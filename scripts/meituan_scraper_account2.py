#!/usr/bin/env python3
"""
美团外卖订单爬虫 — 第二个账号专用 (v2，支持 checkpoint)
======================================================
用法：
  # 第一步：收集所有订单 ID（~2分钟）
  python3 meituan_scraper_account2.py --collect-ids

  # 第二步：分批拉取订单详情（每批100条，可中断续传）
  python3 meituan_scraper_account2.py --fetch-details
"""

import json
import time
import subprocess
import websocket
import os
import sys
import urllib.request
import urllib.parse

CDP_PORT = 9224
USER_DATA_DIR = os.path.expanduser("~/Library/Caches/cookie-cdp-chrome-account2")
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
PRIVATE_OUTPUT = os.path.join(ROOT_DIR, '.private', 'orders.raw.account2.json')
CHECKPOINT_IDS = os.path.join(ROOT_DIR, '.private', 'orders.account2.ids.json')
CHECKPOINT_DETAILS = os.path.join(ROOT_DIR, '.private', 'orders.account2.details.json')
ORDER_LIST_API = "https://i.waimai.meituan.com/openh5/order/list"
ORDER_DETAIL_API = "https://i.waimai.meituan.com/openh5/order/detail"
ORDER_PAGE_URL = "https://h5.waimai.meituan.com/waimai/mindex/olist"


def json_load(path, default=None):
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return default


def json_save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, path)


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
        ORDER_PAGE_URL
    ]
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("🚀 Chrome 启动中...")
    time.sleep(3)


def open_meituan_tab():
    encoded = urllib.parse.quote(ORDER_PAGE_URL, safe="")
    request = urllib.request.Request(
        f"http://127.0.0.1:{CDP_PORT}/json/new?{encoded}",
        method="PUT",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.load(response)


def get_tab():
    deadline = time.time() + 120
    last_error = None
    opened = False
    print("⏳ 等待页面就绪...")
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{CDP_PORT}/json/list', timeout=2) as response:
                tabs = json.load(response)
            matching = [tab for tab in tabs if 'h5.waimai.meituan.com' in tab.get('url', '')]
            if matching and matching[0].get('webSocketDebuggerUrl'):
                return matching[0]['webSocketDebuggerUrl']
            if not opened:
                open_meituan_tab()
                opened = True
        except Exception as error:
            last_error = error
        time.sleep(2)
    raise RuntimeError(f"Chrome 订单页在 120 秒内未就绪: {last_error}")


def cdp_send(ws, method, params=None):
    import uuid
    cmd_id = int(uuid.uuid4().int % 1000000)
    ws.send(json.dumps({'id': cmd_id, 'method': method, 'params': params or {}}))
    while True:
        msg = json.loads(ws.recv())
        if 'id' in msg and msg['id'] == cmd_id:
            if 'error' in msg:
                raise RuntimeError(f"CDP 命令失败: {msg['error']}")
            return msg


def collect_all_order_ids(ws_url):
    """阶段1：只收集订单ID，立即存盘"""
    # 先看有没有之前的 checkpoint
    existing = json_load(CHECKPOINT_IDS, {"ids": [], "cursor": None, "isEnd": False})
    all_ids = existing.get("ids", [])
    cursor = existing.get("cursor")
    if existing.get("isEnd"):
        print(f"📋 已有 {len(all_ids)} 条订单 ID（已完成），跳过收集")
        return all_ids

    ws = websocket.create_connection(ws_url, timeout=30)
    cdp_send(ws, 'Runtime.enable')

    page = len(all_ids) // 10 + 1
    access_deadline = time.time() + 180
    access_notice_shown = False

    print(f"📦 正在收集订单 ID（已收集 {len(all_ids)} 条，从第 {page} 页继续）...")

    while True:
        body_parts = ["yodaReady=h5&csecplatform=4&csecversion=4.2.4"]
        if cursor:
            body_parts.append(f"cursor={cursor}")

        body = "&".join(body_parts)
        body_js = json.dumps(body)

        r = cdp_send(ws, 'Runtime.evaluate', {
            'expression': f'''
            (async () => {{
                const bodyStr = {body_js};
                const resp = await fetch("{ORDER_LIST_API}", {{
                    method: "POST",
                    credentials: "include",
                    headers: {{"Accept":"application/json","Content-Type":"application/x-www-form-urlencoded"}},
                    body: bodyStr
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
            raise RuntimeError(f"美团订单接口未返回数据: {description}")
        result = json.loads(runtime_result['value'])
        if result.get('error'):
            if page == 1 and time.time() < access_deadline:
                if not access_notice_shown:
                    print("🔐 待授权，请在 Chrome 中登录...")
                    access_notice_shown = True
                time.sleep(5)
                continue
            raise RuntimeError(f"美团订单列表不可用: {result}")

        new_ids = result.get('orderIds', [])
        if not new_ids:
            break

        all_ids.extend(new_ids)
        cursor = result.get('cursor', '')
        is_end = result.get('isEnd', False)

        # 每10页存一次 checkpoint
        if page % 10 == 0:
            json_save(CHECKPOINT_IDS, {"ids": all_ids, "cursor": cursor, "isEnd": is_end})

        print(f"  第{page}页: +{len(new_ids)} 条 (累计 {len(all_ids)} 条)")

        if is_end:
            break

        page += 1
        time.sleep(0.3)

    ws.close()
    json_save(CHECKPOINT_IDS, {"ids": all_ids, "cursor": None, "isEnd": True})
    print(f"\n✅ ID 收集完成：共 {len(all_ids)} 条订单")
    return all_ids


def fetch_details_batch(ws_url, order_ids):
    """阶段2：分批拉取详情，支持断点续传"""
    details = json_load(CHECKPOINT_DETAILS, {})
    pending = [oid for oid in order_ids if oid not in details]

    if not pending:
        print(f"✅ 所有 {len(order_ids)} 条订单详情已拉取完毕")
        return [details[oid] for oid in order_ids if oid in details]

    ws = websocket.create_connection(ws_url, timeout=120)
    cdp_send(ws, 'Runtime.enable')

    total = len(order_ids)
    done = len(details)
    print(f"\n📋 正在拉取订单详情（已拉取 {done}/{total}，剩余 {len(pending)}）...")

    for i, oid in enumerate(pending):
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
            details[oid] = json.loads(result)

        # 每 50 条存一次 checkpoint
        if (i + 1) % 50 == 0:
            json_save(CHECKPOINT_DETAILS, details)
            pct = (done + i + 1) / total * 100
            print(f"  进度: {done + i + 1}/{total} ({pct:.1f}%)")

        time.sleep(0.2)

    ws.close()
    json_save(CHECKPOINT_DETAILS, details)

    orders = [details[oid] for oid in order_ids if oid in details]
    orders.sort(key=lambda x: x.get('date', '') + x.get('time', ''), reverse=True)
    return orders


def main():
    if '--collect-ids' in sys.argv:
        print("=" * 60)
        print("  阶段1：收集订单 ID")
        print("=" * 60)
        start_chrome()
        ws_url = get_tab()
        print(f"🔗 已连接 Chrome")
        order_ids = collect_all_order_ids(ws_url)
        print(f"\n✅ 订单 ID 已保存到: {CHECKPOINT_IDS}")
        print(f"   共 {len(order_ids)} 条")
        print(f"   下一步: python3 meituan_scraper_account2.py --fetch-details")

    elif '--fetch-details' in sys.argv:
        print("=" * 60)
        print("  阶段2：拉取订单详情")
        print("=" * 60)
        ids_data = json_load(CHECKPOINT_IDS)
        if not ids_data or not ids_data.get("ids"):
            print("❌ 未找到订单 ID checkpoint，请先运行 --collect-ids")
            sys.exit(1)

        order_ids = ids_data["ids"]
        print(f"📋 共 {len(order_ids)} 条订单待拉取")

        start_chrome()
        ws_url = get_tab()
        print(f"🔗 已连接 Chrome")

        orders = fetch_details_batch(ws_url, order_ids)
        json_save(PRIVATE_OUTPUT, orders)
        print(f"\n📁 订单已保存至: {PRIVATE_OUTPUT}")
        print(f"📊 共 {len(orders)} 条订单详情")

    else:
        print("用法:")
        print("  python3 meituan_scraper_account2.py --collect-ids    # 第一步：收集ID")
        print("  python3 meituan_scraper_account2.py --fetch-details  # 第二步：拉取详情")


if __name__ == '__main__':
    main()
