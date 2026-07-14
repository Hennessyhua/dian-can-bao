#!/usr/bin/env python3
"""
美团外卖订单爬虫 — 点餐宝数据提取工具
=========================================
原理：通过 Chrome DevTools Protocol (CDP) 连接本地已登录的 Chrome，
调用美团 H5 页面内部 API，批量拉取订单数据和详情地址。

使用方法：
  1. 确保 Chrome 已用你的美团账号登录过（Cookie 持久化）
  2. 运行本脚本：python3 meituan_scraper.py
  3. 数据输出到 ../data/orders.json

依赖：Python 3.8+, websocket-client, Chrome 浏览器
安装：pip install websocket-client
"""

import json
import time
import subprocess
import websocket
import os
import urllib.request

# 配置
CDP_PORT = 9223
USER_DATA_DIR = os.path.expanduser("~/Library/Caches/cookie-cdp-chrome")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
ORDER_LIST_API = "https://i.waimai.meituan.com/openh5/order/list"
ORDER_DETAIL_API = "https://i.waimai.meituan.com/openh5/order/detail"

# ============================================================
# 第1步：启动 Chrome（如有头模式可看到浏览器窗口）
# ============================================================
def start_chrome():
    chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    cmd = [
        chrome_path,
        f"--remote-debugging-port={CDP_PORT}",
        f"--user-data-dir={USER_DATA_DIR}",
        "--no-first-run",
        "--disable-background-networking",
        "--disable-sync",
        "--remote-allow-origins=*",
        "--lang=zh-CN",
        "--window-size=430,932",
        "https://h5.waimai.meituan.com/waimai/mindex/olist"
    ]
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("🚀 Chrome 启动中...")
    time.sleep(5)

# ============================================================
# 第2步：连接 CDP 并获取订单数据
# ============================================================
def get_tab():
    """等待订单页就绪，并返回对应标签页的 CDP 地址。"""
    deadline = time.time() + 30
    last_error = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{CDP_PORT}/json/list', timeout=2) as response:
                tabs = json.load(response)
            matching = [tab for tab in tabs if 'h5.waimai.meituan.com' in tab.get('url', '')]
            candidates = matching or tabs
            if candidates and candidates[0].get('webSocketDebuggerUrl'):
                return candidates[0]['webSocketDebuggerUrl']
        except Exception as error:
            last_error = error
        time.sleep(1)
    raise RuntimeError(f"Chrome 订单页在 30 秒内未就绪: {last_error}")

def cdp_send(ws, method, params=None):
    """发送 CDP 命令并等待响应"""
    import uuid
    cmd_id = int(uuid.uuid4().int % 1000000)
    ws.send(json.dumps({'id': cmd_id, 'method': method, 'params': params or {}}))
    while True:
        msg = json.loads(ws.recv())
        if 'id' in msg and msg['id'] == cmd_id:
            if 'error' in msg:
                raise RuntimeError(f"CDP 命令失败: {msg['error']}")
            return msg

def fetch_all_orders(ws_url):
    """分页拉取全部订单"""
    ws = websocket.create_connection(ws_url, timeout=30)
    cdp_send(ws, 'Runtime.enable')
    
    all_ids = []
    cursor = None
    page = 1
    
    print("📦 正在获取订单列表...")
    
    while True:
        body_parts = ["yodaReady=h5&csecplatform=4&csecversion=4.2.4"]
        if cursor:
            body_parts.append(f"cursor={cursor}")
        
        body = "&".join(body_parts)
        
        r = cdp_send(ws, 'Runtime.evaluate', {
            'expression': f'''
            (async () => {{
                const resp = await fetch("{ORDER_LIST_API}", {{
                    method: "POST",
                    credentials: "include",
                    headers: {{"Accept":"application/json","Content-Type":"application/x-www-form-urlencoded"}},
                    body: "{body}"
                }});
                const data = await resp.json();
                return JSON.stringify({{
                    cursor: data.data.cursor,
                    isEnd: data.data.isEnd,
                    orderIds: data.data.orderList.map(o => o.orderId)
                }});
            }})()
            ''',
            'awaitPromise': True,
            'returnByValue': True
        })
        
        result = json.loads(r['result']['result']['value'])
        new_ids = result.get('orderIds', [])
        
        if not new_ids:
            break
        
        all_ids.extend(new_ids)
        cursor = json.dumps(result.get('cursor', ''))
        
        print(f"  第{page}页: +{len(new_ids)} 条 (累计 {len(all_ids)} 条)")
        
        if result.get('isEnd'):
            break
        
        page += 1
        time.sleep(0.5)
    
    ws.close()
    return all_ids

def fetch_order_details(ws_url, order_ids, batch_size=5):
    """批量获取订单详情（含地址）"""
    ws = websocket.create_connection(ws_url, timeout=120)
    cdp_send(ws, 'Runtime.enable')
    
    orders = []
    print(f"\n📋 正在获取 {len(order_ids)} 条订单详情...")
    
    for i, oid in enumerate(order_ids):
        r = cdp_send(ws, 'Runtime.evaluate', {
            'expression': f'''
            (async () => {{
                const resp = await fetch("{ORDER_DETAIL_API}", {{
                    method: "POST",
                    credentials: "include",
                    headers: {{"Accept":"application/json","Content-Type":"application/x-www-form-urlencoded"}},
                    body: "yodaReady=h5&csecplatform=4&csecversion=4.2.4&mtOrderViewId={oid}"
                }});
                const data = await resp.json();
                if (data.code === 0 && data.data) {{
                    const d = data.data;
                    return JSON.stringify({{
                        orderId: d.mtOrderViewId || oid,
                        restaurant: d.shopInfo?.name || "",
                        items: (d.dishes || []).map(x => ({{name: x.name, quantity: x.count}})),
                        date: (d.createTime || "").split(" ")[0] || "",
                        time: (d.createTime || "").split(" ")[1] || "",
                        total: d.payPrice || 0,
                        address: d.receiver?.address || "",
                        receiver: d.receiver?.name || "",
                        phone: d.receiver?.phone || ""
                    }});
                }}
                return "null";
            }})()
            ''',
            'awaitPromise': True,
            'returnByValue': True
        })
        
        result = r['result']['result']['value']
        if result and result != 'null':
            orders.append(json.loads(result))
        
        if (i + 1) % batch_size == 0:
            print(f"  进度: {i+1}/{len(order_ids)}")
        time.sleep(0.3)
    
    ws.close()
    return orders

# ============================================================
# 第3步：主流程
# ============================================================
def scrape_orders():
    """运行完整采集流程并返回订单列表，不写文件。"""
    # 启动 Chrome
    start_chrome()
    
    # 获取 WebSocket 连接地址
    ws_url = get_tab()
    print(f"🔗 已连接 Chrome: {ws_url[:50]}...")
    
    # 拉取全部订单 ID
    order_ids = fetch_all_orders(ws_url)
    print(f"\n✅ 共获取 {len(order_ids)} 条订单 ID")
    
    # 拉取订单详情
    orders = fetch_order_details(ws_url, order_ids)
    print(f"\n✅ 共获取 {len(orders)} 条订单详情")
    
    # 按日期排序
    orders.sort(key=lambda x: x.get('date', '') + x.get('time', ''), reverse=True)
    
    return orders


def save_orders(orders, output_path):
    """以原子替换方式保存私有原始订单。"""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    temp_path = f"{output_path}.tmp"
    with open(temp_path, 'w', encoding='utf-8') as file:
        json.dump(orders, file, ensure_ascii=False, indent=2)
    os.replace(temp_path, output_path)


def main():
    orders = scrape_orders()
    output_path = os.path.join(OUTPUT_DIR, 'orders.json')
    save_orders(orders, output_path)
    print(f"\n📁 私有原始数据已保存至: {output_path}")
    print(f"📊 统计: {len(orders)} 条订单（未输出地址详情）")

if __name__ == '__main__':
    main()
