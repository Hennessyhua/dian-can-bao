#!/bin/zsh
set -euo pipefail

ROOT_DIR="${0:A:h:h}"
cd "$ROOT_DIR"

python3 scripts/update_site_data.py "$@"
python3 -m unittest discover -s tests -p 'test_*.py'
python3 -m py_compile \
  scripts/dish_intelligence.py \
  scripts/update_site_data.py \
  scripts/meituan_scraper.py
(cd web && npm test && npm run build)

python3 - <<'PY'
import json
from pathlib import Path

root = Path.cwd()
payload = json.loads((root / "web/public/data/orders.public.json").read_text())
audit = json.loads((root / ".private/dish-classification.audit.json").read_text())

assert payload["schemaVersion"] == 4
assert payload["classificationVersion"] == audit["classificationVersion"]
assert len({dish["id"] for dish in payload["dishes"]}) == len(payload["dishes"])
assert all(
    item.get("mealPeriod") in {"breakfast", "lunch", "dinner"} and item.get("dishId")
    for order in payload["orders"]
    for item in order["items"]
)

print(
    "Hermes 数据更新完成："
    f"{payload['publishedOrderCount']} 条订单，"
    f"{len(payload['dishes'])} 个去重菜品，"
    f"分类版本 {payload['classificationVersion']}"
)
PY
