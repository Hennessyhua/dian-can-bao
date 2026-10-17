#!/usr/bin/env python3
"""批量获取订单详情，带检查点续传和限速保护。

用法：
  python3 scripts/fetch_details_batch.py --ids .private/orders.account2.ids.json
  python3 scripts/fetch_details_batch.py --ids .private/orders.account2.ids.json --resume
"""

import argparse
import json
import os
import sys
import time
import urllib.request
import websocket

CDP_PORT = 9224
ORDER_DETAIL_API = "https://i.waimai.meituan.com/openh5/order/detail"
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

def cdp_send(ws, method, params=None):
    import uuid
    cmd_id = int(uuid.uuid4().int % 1000000)
    ws.send(json.dumps({'id': cmd_id, 'method': method, 'params': params or {}}))
    while True:
        msg = json.loads(ws.recv())
        if 'id' in msg and msg['id'] == cmd_id:
            if 'error' in msg:
                raise RuntimeError(f"CDP error: {msg['error']}")
            return msg

def get_ws_url():
    with urllib.request.urlopen(f'http://127.0.0.1:{CDP_PORT}/json/list', timeout=3) as r:
        tabs = json.load(r)
    for tab in tabs:
        if 'waimai.meituan.com' in tab.get('url', ''):
            return tab.get('webSocketDebuggerUrl')
    raise RuntimeError("No Meituan tab found on port 9224")

def fetch_detail(ws, oid):
    """Fetch single order detail, returns dict or None."""
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
        return json.loads(result)
    return None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ids', required=True, help='Path to orders IDs JSON file')
    parser.add_argument('--resume', action='store_true', help='Resume from checkpoint')
    parser.add_argument('--output', default='.private/orders.raw.json', help='Output path')
    parser.add_argument('--max-orders', type=int, default=0, help='Max orders to fetch (0=all)')
    parser.add_argument('--delay', type=float, default=1.0, help='Delay between fetches')
    parser.add_argument('--batch-size', type=int, default=5, help='Console report interval')
    args = parser.parse_args()

    ids_path = args.ids if args.ids.startswith('/') else os.path.join(ROOT_DIR, args.ids)
    output_path = args.output if args.output.startswith('/') else os.path.join(ROOT_DIR, args.output)
    checkpoint_path = output_path + '.checkpoint'

    # Load order IDs
    with open(ids_path) as f:
        all_ids = json.load(f).get('ids', [])
    print(f"📋 共 {len(all_ids)} 条订单 ID")

    if args.max_orders > 0 and args.max_orders < len(all_ids):
        all_ids = all_ids[:args.max_orders]
        print(f"  限制获取前 {args.max_orders} 条")

    # Load checkpoint if resuming
    done_ids = set()
    existing_orders = []
    if args.resume and os.path.exists(checkpoint_path):
        with open(checkpoint_path) as f:
            cp = json.load(f)
        done_ids = set(cp.get('done_ids', []))
        existing_orders = cp.get('orders', [])
        print(f"📌 检查点续传：已有 {len(existing_orders)} 条，剩余 {len(all_ids) - len(done_ids)} 条")

    # WebSocket connection
    ws_url = get_ws_url()
    print(f"🔗 已连接 Chrome: {ws_url[:60]}...")
    ws = websocket.create_connection(ws_url, timeout=120)
    cdp_send(ws, 'Runtime.enable')

    orders = list(existing_orders)
    retry_count = 0
    max_retries = 5

    try:
        for i, oid in enumerate(all_ids):
            if oid in done_ids:
                continue

            # Attempt with retries
            detail = None
            for attempt in range(max_retries):
                try:
                    detail = fetch_detail(ws, oid)
                    if detail:
                        break
                    # null response - wait and retry
                    print(f"  ⚠️ [{i+1}/{len(all_ids)}] 订单 {oid[:12]}... 返回空，重试...")
                    time.sleep(2)
                except Exception as e:
                    # Reconnect on WS error
                    if attempt < max_retries - 1:
                        print(f"  ⚠️ [{i+1}/{len(all_ids)}] 连接错误: {e}，重连...")
                        try:
                            ws.close()
                        except:
                            pass
                        time.sleep(3)
                        ws = websocket.create_connection(ws_url, timeout=120)
                        cdp_send(ws, 'Runtime.enable')
                        time.sleep(1)
                    else:
                        print(f"  ❌ [{i+1}/{len(all_ids)}] 订单 {oid[:12]}... 失败")

            if detail:
                orders.append(detail)
                done_ids.add(oid)

            # Progress report & checkpoint
            if (i + 1) % args.batch_size == 0:
                print(f"  📊 进度: {len(done_ids)}/{len(all_ids)} (成功: {len(orders)})")
                # Save checkpoint
                os.makedirs(os.path.dirname(checkpoint_path), exist_ok=True)
                with open(checkpoint_path + '.tmp', 'w') as f:
                    json.dump({'done_ids': list(done_ids), 'orders': orders}, f,
                              ensure_ascii=False)
                os.replace(checkpoint_path + '.tmp', checkpoint_path)

            time.sleep(args.delay)

    finally:
        ws.close()

    # Sort by date descending
    orders.sort(key=lambda x: x.get('date', '') + x.get('time', ''), reverse=True)

    # Save final output
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path + '.tmp', 'w') as f:
        json.dump(orders, f, ensure_ascii=False, indent=2)
    os.replace(output_path + '.tmp', output_path)

    # Clean up checkpoint
    if os.path.exists(checkpoint_path):
        os.remove(checkpoint_path)

    # Stats
    dates = [o.get('date', '') for o in orders if o.get('date')]
    print(f"\n✅ 完成！共 {len(orders)} 条订单")
    if dates:
        print(f"   时间范围: {dates[-1]} ~ {dates[0]}")
    restaurants = set(o.get('restaurant', '') for o in orders if o.get('restaurant'))
    print(f"   餐厅数: {len(restaurants)}")
    total = sum(o.get('total', 0) for o in orders)
    print(f"   总消费: ¥{total:.2f}")
    print(f"   输出: {output_path}")

if __name__ == '__main__':
    main()
