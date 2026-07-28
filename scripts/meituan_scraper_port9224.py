#!/usr/bin/env python3
"""美团外卖订单爬虫 — 连接到已有 Chrome (port 9224) 版本。

与 meituan_scraper.py 的区别：
- 不启动新 Chrome，直接连接 port 9224 上已登录的 Chrome
- 兼容现有 pipeline：产出与 meituan_scraper.py 相同的订单结构
"""

import json
import time
import urllib.request
import urllib.parse
import os
import sys
import websocket

CDP_PORT = 9224
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
PRIVATE_OUTPUT = os.path.join(ROOT_DIR, '.private', 'orders.raw.json')
ORDER_LIST_API = "https://i.waimai.meituan.com/openh5/order/list"
ORDER_DETAIL_API = "https://i.waimai.meituan.com/openh5/order/detail"

def get_tabs():
    """获取指定端口上的所有 Chrome 标签页"""
    with urllib.request.urlopen(f'http://127.0.0.1:{CDP_PORT}/json/list', timeout=3) as resp:
        return json.load(resp)

def find_meituan_tab():
    """找到已有的美团订单页标签"""
    tabs = get_tabs()
    for tab in tabs:
        url = tab.get('url', '')
        if 'h5.waimai.meituan.com' in url or 'waimai.meituan.com' in url:
            ws_url = tab.get('webSocketDebuggerUrl')
            if ws_url:
                print(f"🔍 找到美团标签页: {tab.get('title','')}")
                print(f"   URL: {url[:100]}...")
                return ws_url
    return None

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

def navigate_to_orders(ws_url):
    """导航到订单页（如果当前不在）"""
    ws = websocket.create_connection(ws_url, timeout=15)
    # 先检查当前页面
    r = cdp_send(ws, 'Runtime.evaluate', {
        'expression': 'window.location.href',
        'returnByValue': True
    })
    current_url = r.get('result', {}).get('result', {}).get('value', '')
    if 'olist' not in current_url and 'order/list' not in current_url:
        print("📌 正在导航到订单列表页...")
        cdp_send(ws, 'Page.navigate', {'url': 'https://h5.waimai.meituan.com/waimai/mindex/olist'})
        time.sleep(3)
    ws.close()

def fetch_all_orders(ws_url):
    """分页拉取全部订单（兼容一年数据）"""
    ws = websocket.create_connection(ws_url, timeout=30)
    cdp_send(ws, 'Runtime.enable')

    all_ids = []
    cursor_str = None
    page = 1
    access_deadline = time.time() + 180
    access_notice_shown = False

    print("📦 正在获取订单列表...")

    while True:
        # Use URLSearchParams on JS side to avoid string injection issues
        cursor_js = json.dumps(cursor_str) if cursor_str else 'null'

        r = cdp_send(ws, 'Runtime.evaluate', {
            'expression': f'''
            (async () => {{
                const params = new URLSearchParams();
                params.append("yodaReady", "h5");
                params.append("csecplatform", "4");
                params.append("csecversion", "4.2.4");
                if ({cursor_js}) {{
                    params.append("cursor", {cursor_js});
                }}
                const resp = await fetch("{ORDER_LIST_API}", {{
                    method: "POST",
                    credentials: "include",
                    headers: {{"Accept":"application/json","Content-Type":"application/x-www-form-urlencoded"}},
                    body: params.toString()
                }});
                const text = await resp.text();
                let data = null;
                try {{ data = JSON.parse(text); }} catch (error) {{}}
                if (!resp.ok || !data?.data?.orderList) {{
                    return JSON.stringify({{
                        error: "ORDER_LIST_UNAVAILABLE",
                        httpStatus: resp.status,
                        code: data?.code ?? null,
                        message: data?.msg || data?.message || ""
                    }});
                }}
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

        runtime_result = r.get('result', {}).get('result', {})
        if runtime_result.get('type') != 'string':
            description = runtime_result.get('description') or runtime_result.get('value') or runtime_result
            raise RuntimeError(f"美团订单接口未返回订单数据: {description}")
        result = json.loads(runtime_result['value'])

        if result.get('error'):
            if page == 1 and time.time() < access_deadline:
                if not access_notice_shown:
                    print("🔐 美团订单接口尚未授权，请在 Chrome 中完成登录或验证；脚本将在 3 分钟内自动重试...")
                    access_notice_shown = True
                time.sleep(5)
                continue
            # 403 rate limit - wait and retry
            if result.get('httpStatus') == 403:
                retry_wait = min(30, 5 + page * 2)
                print(f"  ⚠️ 403 限流，等待 {retry_wait}s 后重试...")
                time.sleep(retry_wait)
                continue
            raise RuntimeError(
                "美团订单列表暂不可用"
                f"（HTTP {result.get('httpStatus')}，code={result.get('code')}）。"
                "请在打开的 Chrome 美团订单页完成登录或验证后重新运行。"
            )

        new_ids = result.get('orderIds', [])
        if not new_ids:
            break

        all_ids.extend(new_ids)
        cursor_str = result.get('cursor', '')

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

def scrape_orders():
    """连接到已有 Chrome 并抓取订单"""
    print(f"🔗 连接 Chrome (端口 {CDP_PORT})...")

    # 检查 Chrome 是否在运行
    try:
        tabs = get_tabs()
        print(f"  发现 {len(tabs)} 个标签页")
    except Exception as e:
        raise RuntimeError(f"无法连接到端口 {CDP_PORT} 的 Chrome。请确认已经打开带 remote debugging 的 Chrome。错误: {e}")

    # 查找美团标签页
    ws_url = find_meituan_tab()
    if not ws_url:
        raise RuntimeError("未找到美团订单页标签。请在 Chrome 中打开 https://h5.waimai.meituan.com/waimai/mindex/olist")

    # 确保在订单页
    navigate_to_orders(ws_url)

    # 拉取订单 ID 列表
    order_ids = fetch_all_orders(ws_url)
    print(f"\n✅ 共获取 {len(order_ids)} 条订单 ID")

    # 拉取订单详情
    orders = fetch_order_details(ws_url, order_ids)
    print(f"\n✅ 共获取 {len(orders)} 条订单详情")

    # 按日期排序（最新在前）
    orders.sort(key=lambda x: x.get('date', '') + x.get('time', ''), reverse=True)

    return orders

def main():
    print("=" * 50)
    print("🍽️  点餐宝 — 美团订单采集（连接已有 Chrome）")
    print("=" * 50)

    orders = scrape_orders()

    # 保存原始数据
    os.makedirs(os.path.dirname(PRIVATE_OUTPUT), exist_ok=True)
    temp_path = f"{PRIVATE_OUTPUT}.tmp"
    with open(temp_path, 'w', encoding='utf-8') as f:
        json.dump(orders, f, ensure_ascii=False, indent=2)
    os.replace(temp_path, PRIVATE_OUTPUT)
    print(f"\n📁 私有原始数据已保存至: {PRIVATE_OUTPUT}")
    print(f"   订单数: {len(orders)}")

    # 计算时间跨度
    if orders:
        dates = [o.get('date', '') for o in orders if o.get('date')]
        if dates:
            print(f"   时间范围: {dates[-1]} ~ {dates[0]}")
        total = sum(o.get('total', 0) for o in orders)
        print(f"   总消费: ¥{total:.2f}")

        # 统计来源
        restaurants = set()
        for o in orders:
            if o.get('restaurant'):
                restaurants.add(o['restaurant'])
        print(f"   餐厅数: {len(restaurants)}")

    # 现在通过现有 pipeline 生成公开数据
    print("\n" + "=" * 50)
    print("🔄 通过 update_site_data.py 进行数据清洗与发布...")
    print("=" * 50)

    # 将 meituan_scraper 路径加入 sys.path 以便 import
    sys.path.insert(0, os.path.join(ROOT_DIR, 'scripts'))
    from update_site_data import (
        PRIVATE_CLASSIFICATION_AUDIT,
        PUBLIC_OUTPUT,
        assert_public_payload_is_safe,
        atomic_write_json,
        build_public_payload_with_audit,
        load_json,
        merge_orders,
    )

    # 合并已有订单
    existing = load_json(PRIVATE_OUTPUT, [])
    merged = merge_orders(existing, [])  # 刚刚已是最新数据，但保留 merge 逻辑
    atomic_write_json(PRIVATE_OUTPUT, merged)

    # 构建并检查公开数据
    payload, audit = build_public_payload_with_audit(merged)
    assert_public_payload_is_safe(payload)
    atomic_write_json(PUBLIC_OUTPUT, payload)
    atomic_write_json(PRIVATE_CLASSIFICATION_AUDIT, audit)

    print(f"\n📊 原始订单: {payload['sourceOrderCount']} 条")
    print(f"📊 可推荐订单: {payload['publishedOrderCount']} 条")
    print(f"🍽️  独立菜品: {payload['uniqueMealItems']} 道")
    print(f"⛔ 排除附属/非餐饮: {payload['uniqueExcludedItems']} 项")
    print(f"🌐 脱敏数据已刷新: {PUBLIC_OUTPUT}")
    print(f"📋 逐项分类审计: {PRIVATE_CLASSIFICATION_AUDIT}")

if __name__ == '__main__':
    main()
