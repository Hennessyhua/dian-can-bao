#!/usr/bin/env python3
"""更新点餐宝公开数据。

默认读取现有私有订单并生成 GitHub Pages 可用的脱敏 JSON：
    python3 scripts/update_site_data.py

重新从美团采集并生成公开数据：
    python3 scripts/update_site_data.py --scrape
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_DIR = ROOT / ".private"
PRIVATE_RAW = PRIVATE_DIR / "orders.raw.json"
LEGACY_RAW = ROOT / "data" / "orders.json"
PUBLIC_OUTPUT = ROOT / "web" / "public" / "data" / "orders.public.json"
PRIVATE_LOCATION_MAP = PRIVATE_DIR / "location-map.json"

LOCATIONS = {
    "home_xuhui": {
        "code": "home_xuhui",
        "label": "家（徐汇电影华苑）",
        "shortLabel": "家 · 徐汇电影华苑",
    },
    "office_xintiandi": {
        "code": "office_xintiandi",
        "label": "新天地（徕卡办公室）",
        "shortLabel": "新天地 · 徕卡办公室",
    },
}

NON_FOOD_ITEM_PATTERN = re.compile(
    r"餐具|包装袋|打包袋|纸巾|发票|验孕|试纸|感冒灵|口罩|手机防水袋",
    re.IGNORECASE,
)

# 兼容商家常见的中英文括号混用，例如 `（半份5片)`。
BRACKET_NOTE_PATTERN = re.compile(r"[【\[（(][^】\]）)]*[】\]）)]")
LEADING_DECORATION_PATTERN = re.compile(r"^[\s·•✦★☆🌟➕+丨|｜:：!！—_-]+")
MARKETING_PREFIX_PATTERN = re.compile(
    r"^(?:销量TOP|TOP|爆款|热销|人气王|门店招牌|招牌必点|经典|精选|尝鲜|直播专享|"
    r"收藏特惠|收藏门店|福利加料|福利|特惠|限时特惠|新客特惠|新年特惠|"
    r"元气满满|好吃入味|优选好物|超豪华)\s*[丨|｜:：!！·-]*\s*",
    re.IGNORECASE,
)


def normalize_address(value: str) -> str:
    return "".join(str(value or "").strip().lower().split())


def address_hash(value: str) -> str:
    return hashlib.sha256(normalize_address(value).encode("utf-8")).hexdigest()


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    with temp_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write("\n")
    os.replace(temp_path, path)


def load_private_location_map() -> dict[str, str]:
    payload = load_json(PRIVATE_LOCATION_MAP, {}) or {}
    mapping = payload.get("addressHashToLocation", {})
    return {key: value for key, value in mapping.items() if value in LOCATIONS}


def resolve_location(address: str, private_mapping: dict[str, str]) -> str | None:
    normalized = normalize_address(address)
    mapped = private_mapping.get(address_hash(address))
    if mapped:
        return mapped
    if "电影华苑" in normalized:
        return "home_xuhui"
    if "新天地" in normalized or "徕卡" in normalized:
        return "office_xintiandi"
    return None


def order_key(order: dict[str, Any]) -> str:
    # 始终使用内容指纹，兼容旧数据没有 orderId、新数据带 orderId 的情况。
    # 时间、餐厅、菜品和金额共同参与，避免首次升级时把全部历史订单重复一遍。
    fingerprint = {
        "restaurant": order.get("restaurant"),
        "items": order.get("items"),
        "date": order.get("date"),
        "time": order.get("time"),
        "total": order.get("total"),
    }
    encoded = json.dumps(fingerprint, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return f"fp:{hashlib.sha256(encoded).hexdigest()}"


def clean_dish_name(value: str) -> str:
    """移除营销标签、装饰符号和括号说明，只保留可识别的菜品名称。"""
    name = str(value or "").strip()
    previous = None
    while name and name != previous:
        previous = name
        name = BRACKET_NOTE_PATTERN.sub("", name)
        name = LEADING_DECORATION_PATTERN.sub("", name).strip()
        name = MARKETING_PREFIX_PATTERN.sub("", name).strip()

    # 清理删除标签后遗留在名称两端的分隔符，但保留名称中间的组合信息。
    name = re.sub(r"^[\s丨|｜:：!！·—_-]+|[\s丨|｜:：!！·—_-]+$", "", name)
    return re.sub(r"\s{2,}", " ", name).strip()


def merge_orders(existing: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged = {order_key(order): order for order in existing if isinstance(order, dict)}
    merged.update({order_key(order): order for order in incoming if isinstance(order, dict)})
    return sorted(
        merged.values(),
        key=lambda order: f"{order.get('date', '')} {order.get('time', '')}",
        reverse=True,
    )


def sanitize_order(order: dict[str, Any], private_mapping: dict[str, str]) -> dict[str, Any] | None:
    location_code = resolve_location(str(order.get("address") or ""), private_mapping)
    if not location_code:
        return None

    restaurant = str(order.get("restaurant") or "").strip()
    date = str(order.get("date") or "").strip()
    items = []
    for item in order.get("items") or []:
        if not isinstance(item, dict):
            continue
        raw_name = str(item.get("name") or "").strip()
        if not raw_name or NON_FOOD_ITEM_PATTERN.search(raw_name):
            continue
        name = clean_dish_name(raw_name)
        if not name:
            continue
        try:
            quantity = max(1, int(item.get("quantity") or 1))
        except (TypeError, ValueError):
            quantity = 1
        items.append({"name": name, "quantity": quantity})

    if not restaurant or not date or not items:
        return None

    location = LOCATIONS[location_code]
    return {
        "restaurant": restaurant,
        "items": items,
        "date": date,
        "time": str(order.get("time") or "").strip(),
        "total": round(float(order.get("total") or 0), 2),
        "locationCode": location_code,
        "locationLabel": location["label"],
    }


def build_public_payload(raw_orders: list[dict[str, Any]]) -> dict[str, Any]:
    private_mapping = load_private_location_map()
    public_orders = [
        sanitized
        for order in raw_orders
        if isinstance(order, dict)
        for sanitized in [sanitize_order(order, private_mapping)]
        if sanitized is not None
    ]
    public_orders.sort(key=lambda order: f"{order['date']} {order['time']}", reverse=True)
    return {
        "schemaVersion": 2,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sourceOrderCount": len(raw_orders),
        "publishedOrderCount": len(public_orders),
        "locations": list(LOCATIONS.values()),
        "orders": public_orders,
    }


def assert_public_payload_is_safe(payload: dict[str, Any]) -> None:
    forbidden_keys = {"address", "receiver", "phone", "orderId", "cookie", "token"}

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            found = forbidden_keys.intersection(value)
            if found:
                raise ValueError(f"公开数据包含禁止字段: {', '.join(sorted(found))}")
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(payload)


def scrape_and_merge() -> list[dict[str, Any]]:
    from meituan_scraper import scrape_orders

    print("正在打开美团订单页，请在浏览器中完成登录或验证…")
    incoming = scrape_orders()
    existing = load_json(PRIVATE_RAW, None)
    if existing is None:
        existing = load_json(LEGACY_RAW, []) or []
    merged = merge_orders(existing, incoming)
    atomic_write_json(PRIVATE_RAW, merged)
    print(f"私有原始订单已更新：{len(merged)} 条")
    return merged


def main() -> None:
    parser = argparse.ArgumentParser(description="生成点餐宝 GitHub Pages 脱敏数据")
    parser.add_argument("--scrape", action="store_true", help="先从美团重新采集，再生成公开数据")
    args = parser.parse_args()

    if args.scrape:
        raw_orders = scrape_and_merge()
    else:
        source = PRIVATE_RAW if PRIVATE_RAW.exists() else LEGACY_RAW
        raw_orders = load_json(source, []) or []
        if not raw_orders:
            raise SystemExit("没有找到私有订单。请先运行 python3 scripts/update_site_data.py --scrape")

    payload = build_public_payload(raw_orders)
    assert_public_payload_is_safe(payload)
    atomic_write_json(PUBLIC_OUTPUT, payload)
    excluded = payload["sourceOrderCount"] - payload["publishedOrderCount"]
    print(f"公开数据已生成：{payload['publishedOrderCount']} 条，未识别地点排除 {excluded} 条")
    print(f"输出：{PUBLIC_OUTPUT}")
    print("下一步提交并推送 GitHub，Pages 会自动更新。")


if __name__ == "__main__":
    main()
