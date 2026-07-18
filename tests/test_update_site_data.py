import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "update_site_data.py"
SPEC = importlib.util.spec_from_file_location("update_site_data", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PublicDataTests(unittest.TestCase):
    def test_home_address_is_mapped_and_private_fields_are_removed(self):
        raw = [{
            "orderId": "secret-order",
            "restaurant": "测试餐厅",
            "items": [{"name": "测试菜品", "quantity": 1}],
            "date": "2026-07-14",
            "time": "12:00",
            "total": 35.5,
            "address": "上海市某区电影华苑某号",
            "receiver": "某人",
            "phone": "13800000000",
        }]
        payload = MODULE.build_public_payload(raw)
        MODULE.assert_public_payload_is_safe(payload)
        order = payload["orders"][0]
        self.assertEqual(order["locationCode"], "home_xuhui")
        self.assertEqual(order["locationLabel"], "家（徐汇电影华苑）")
        for key in ("orderId", "address", "receiver", "phone"):
            self.assertNotIn(key, order)

    def test_unknown_address_is_not_published(self):
        raw = [{
            "restaurant": "测试餐厅",
            "items": [{"name": "测试菜品", "quantity": 1}],
            "date": "2026-07-14",
            "total": 20,
            "address": "无法识别的位置",
        }]
        payload = MODULE.build_public_payload(raw)
        self.assertEqual(payload["publishedOrderCount"], 0)

    def test_non_food_accessories_are_not_recommendable(self):
        raw = [{
            "restaurant": "测试餐厅",
            "items": [
                {"name": "一次性餐具", "quantity": 1},
                {"name": "嫩牛肉冒菜", "quantity": 1},
            ],
            "date": "2026-07-14",
            "time": "12:00",
            "total": 30,
            "address": "电影华苑",
        }]
        payload = MODULE.build_public_payload(raw)
        items = payload["orders"][0]["items"]
        self.assertEqual([item["name"] for item in items], ["嫩牛肉冒菜"])
        self.assertEqual(items[0]["mealPeriod"], "lunch")
        self.assertTrue(items[0]["dishId"])

    def test_rice_flavor_and_non_food_are_removed_at_order_level(self):
        raw = [{
            "restaurant": "成都你六姐·牛肉冒菜",
            "items": [
                {"name": "【销量TOP】霸气嫩牛套餐（包含米饭x1）", "quantity": 1},
                {"name": "六姐麻辣", "quantity": 1},
                {"name": "五常稻花香米饭", "quantity": 1},
                {"name": "需要餐具", "quantity": 1},
            ],
            "date": "2026-07-14",
            "time": "18:30",
            "total": 40,
            "address": "电影华苑",
        }]
        payload, audit = MODULE.build_public_payload_with_audit(raw)
        self.assertEqual([item["name"] for item in payload["orders"][0]["items"]], ["霸气嫩牛套餐"])
        self.assertEqual(payload["orders"][0]["items"][0]["mealPeriod"], "dinner")
        excluded = {row["name"] for row in audit["items"] if not row["keep"]}
        self.assertEqual(excluded, {"六姐麻辣", "五常稻花香米饭", "需要餐具"})

    def test_future_items_use_order_context_instead_of_one_keyword(self):
        raw = [{
            "restaurant": "测试餐厅",
            "items": [
                {"name": "黑椒牛肉炒饭", "quantity": 1},
                {"name": "原味蘸料", "quantity": 1},
            ],
            "date": "2026-07-14",
            "time": "12:30",
            "total": 30,
            "address": "电影华苑",
        }]
        payload, audit = MODULE.build_public_payload_with_audit(raw)
        self.assertEqual([item["name"] for item in payload["orders"][0]["items"]], ["黑椒牛肉炒饭"])
        sources = {row["name"]: row["source"] for row in audit["items"]}
        self.assertEqual(sources, {"原味蘸料": "inferred", "黑椒牛肉炒饭": "inferred"})

    def test_every_published_item_has_valid_meal_period(self):
        raw = [{
            "restaurant": "皇不管夜包子",
            "items": [{"name": "鲜肉小笼包", "quantity": 1}],
            "date": "2026-07-14",
            "time": "08:30",
            "total": 20,
            "address": "电影华苑",
        }]
        payload = MODULE.build_public_payload(raw)
        self.assertEqual(payload["schemaVersion"], 4)
        self.assertEqual(payload["orders"][0]["items"][0]["mealPeriod"], "breakfast")

    def test_snacks_are_published_in_their_own_period(self):
        raw = [{
            "restaurant": "测试奶茶店",
            "items": [{"name": "杨梅百香观音", "quantity": 1}],
            "date": "2026-07-14",
            "time": "14:30",
            "total": 20,
            "address": "新茂大厦",
        }]
        payload, audit = MODULE.build_public_payload_with_audit(raw)
        self.assertEqual(payload["publishedOrderCount"], 1)
        self.assertEqual(payload["orders"][0]["items"][0]["mealPeriod"], "snack")
        self.assertEqual(audit["items"][0]["source"], "curated")

    def test_same_dish_across_dates_branches_and_reviewed_aliases_has_one_id(self):
        raw = [
            {
                "restaurant": "成都你六姐·牛肉冒菜（上海光启城店）",
                "items": [{"name": "六姐霸气嫩牛套餐", "quantity": 1}],
                "date": "2026-07-14",
                "time": "18:30",
                "total": 40,
                "address": "电影华苑",
            },
            {
                "restaurant": "成都你六姐·牛肉冒菜（另一分店）",
                "items": [{"name": "霸气嫩牛套餐", "quantity": 1}],
                "date": "2026-06-14",
                "time": "19:00",
                "total": 42,
                "address": "电影华苑",
            },
        ]
        payload, audit = MODULE.build_public_payload_with_audit(raw)
        self.assertEqual(payload["uniqueKeptSourceItems"], 2)
        self.assertEqual(payload["uniqueMealItems"], 1)
        self.assertEqual(len(payload["dishes"]), 1)
        self.assertEqual(payload["dishes"][0]["name"], "霸气嫩牛套餐")
        dish_ids = {order["items"][0]["dishId"] for order in payload["orders"]}
        self.assertEqual(len(dish_ids), 1)
        canonical = {row["name"]: row.get("canonicalName") for row in audit["items"]}
        self.assertEqual(canonical["六姐霸气嫩牛套餐"], "霸气嫩牛套餐")

    def test_dish_name_removes_marketing_prefix_and_bracket_notes(self):
        examples = {
            "【销量TOP】霸气嫩牛套餐（菜品不支持更换/包含米饭x1）": "霸气嫩牛套餐",
            "【直播专享】椒麻鸡腿饭（例汤）": "椒麻鸡腿饭",
            "·六姐霸气嫩牛套餐（套餐菜品不支持更换）": "六姐霸气嫩牛套餐",
            "🌟🌟🌟五常稻花香米饭": "五常稻花香米饭",
            "福利加料 | 响铃卷【点💗收藏】": "响铃卷",
            "【尝鲜】武林香辣鸭头（半份5片)": "武林香辣鸭头",
            "Amazing（浮云MG香草籽珍珠酪酪金骏眉冰博克）(660毫升 热 不额外加糖【J0】)": "Amazing",
            "『爆款🔥』大份黄焖鸡+10任选3配菜+香米饭": "大份黄焖鸡+10任选3配菜+香米饭",
        }
        for source, expected in examples.items():
            with self.subTest(source=source):
                self.assertEqual(MODULE.clean_dish_name(source), expected)

    def test_merge_deduplicates_legacy_order_without_order_id(self):
        legacy = {
            "restaurant": "测试餐厅",
            "items": [{"name": "嫩牛肉冒菜", "quantity": 1}],
            "date": "2026-07-14",
            "time": "12:00",
            "total": 30,
            "address": "电影华苑",
        }
        incoming = {**legacy, "orderId": "new-external-id"}
        merged = MODULE.merge_orders([legacy], [incoming])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["orderId"], "new-external-id")

    def test_merge_keeps_distinct_orders_from_two_accounts(self):
        account1 = {
            "restaurant": "旧账号餐厅", "items": [{"name": "牛肉饭", "quantity": 1}],
            "date": "2026-01-01", "time": "12:00", "total": 30,
            "address": "电影华苑",
        }
        account2 = {
            "orderId": "account2-order", "restaurant": "新账号餐厅",
            "items": [{"name": "鸡肉饭", "quantity": 1}],
            "date": "2026-07-01", "time": "18:00", "total": 35,
            "address": "新茂大厦",
        }
        merged = MODULE.merge_orders([account1], [account2])
        self.assertEqual(len(merged), 2)
        self.assertEqual([order["date"] for order in merged], ["2026-07-01", "2026-01-01"])


if __name__ == "__main__":
    unittest.main()
