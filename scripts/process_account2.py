#!/usr/bin/env python3
"""
After scraping account2 orders from Meituan, run this script to:
1. Build location mapping for the new account's addresses
2. Run the full update pipeline
3. Rebuild the web frontend
"""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_RAW = ROOT / ".private" / "orders.raw.json"
LOCATION_MAP_PATH = ROOT / ".private" / "location-map.json"

def normalize_address(value: str) -> str:
    return "".join(str(value or "").strip().lower().split())

def address_hash(value: str) -> str:
    return hashlib.sha256(normalize_address(value).encode("utf-8")).hexdigest()

LOCATIONS = {
    "home_xuhui": "家（徐汇电影华苑）",
    "office_xintiandi": "新天地（徕卡办公室）",
}

# Determine location from address keyword
def guess_location(address: str):
    """Determine location from address keyword. Returns location code or None."""
    norm = normalize_address(address)
    if "电影华苑" in norm:
        return "home_xuhui"
    if "新天地" in norm or "徕卡" in norm or "新茂" in norm:
        return "office_xintiandi"
    return None

def main():
    # 1. Load raw data
    if not PRIVATE_RAW.exists():
        print(f"❌ 未找到原始订单数据: {PRIVATE_RAW}")
        print("   请先运行 python3 scripts/fetch_details_batch.py")
        sys.exit(1)

    with open(PRIVATE_RAW, "r", encoding="utf-8") as f:
        orders = json.load(f)

    print(f"📊 原始订单: {len(orders)} 条")

    # 2. Build location mapping for new addresses
    address_map = {}
    for order in orders:
        addr = order.get("address", "")
        if not addr:
            continue
        h = address_hash(addr)
        if h not in address_map:
            loc = guess_location(addr)
            if loc:
                address_map[h] = loc
                print(f"  📍 {addr[:45]:45s} → {LOCATIONS.get(loc, loc)}")

    # 3. Load existing location map and merge
    existing_map = {}
    if LOCATION_MAP_PATH.exists():
        with open(LOCATION_MAP_PATH, "r", encoding="utf-8") as f:
            existing = json.load(f)
        existing_map = existing.get("addressHashToLocation", {})

    # Merge: new mappings take priority (update if changed)
    merged_map = {**existing_map, **address_map}

    # 4. Save location map
    LOCATION_MAP_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOCATION_MAP_PATH, "w", encoding="utf-8") as f:
        json.dump({"addressHashToLocation": merged_map}, f, ensure_ascii=False, indent=2)
    print(f"\n📁 位置映射已保存 ({len(merged_map)} 条)")

    # Log new additions
    new_entries = {k: v for k, v in address_map.items() if k not in existing_map}
    if new_entries:
        print(f"  新增 {len(new_entries)} 条映射:")
        for h, loc in new_entries.items():
            # Find sample address
            matching = [o["address"] for o in orders if address_hash(o.get("address", "")) == h]
            sample = matching[0][:45] if matching else h[:12]
            print(f"    {sample} → {LOCATIONS.get(loc, loc)}")

    # 5. Run the standard update pipeline
    print("\n" + "=" * 50)
    print("🔄 运行 update_site_data.py...")
    print("=" * 50)

    result = subprocess.run(
        [sys.executable, "scripts/update_site_data.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(f"❌ update_site_data.py 失败:\n{result.stderr}")
        sys.exit(1)

    # 6. Rebuild web frontend
    print("\n" + "=" * 50)
    print("🏗️  重建前端...")
    print("=" * 50)

    result = subprocess.run(
        ["npm", "run", "build"],
        cwd=str(ROOT / "web"),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"❌ 前端构建失败:\n{result.stderr}")
        sys.exit(1)
    print("✅ 前端构建成功")

    # 7. Verify output
    public_path = ROOT / "web" / "public" / "data" / "orders.public.json"
    with open(public_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    print(f"\n{'='*50}")
    print(f"✅ 完成！点餐宝数据更新成功")
    print(f"{'='*50}")
    print(f"  原始订单: {payload['sourceOrderCount']} 条")
    print(f"  可推荐订单: {payload['publishedOrderCount']} 条")
    print(f"  独立菜品: {payload['uniqueMealItems']} 道")
    print(f"  地点数: {len(payload['locations'])}")
    for loc in payload['locations']:
        print(f"    {loc['label']}")
    print(f"\n  脱敏数据: web/public/data/orders.public.json")
    print(f"  本地预览: cd web && npm run dev")

if __name__ == "__main__":
    main()
