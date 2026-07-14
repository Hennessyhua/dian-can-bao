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
            "total": 30,
            "address": "电影华苑",
        }]
        payload = MODULE.build_public_payload(raw)
        self.assertEqual(payload["orders"][0]["items"], [{"name": "嫩牛肉冒菜", "quantity": 1}])

    def test_dish_name_removes_marketing_prefix_and_bracket_notes(self):
        examples = {
            "【销量TOP】霸气嫩牛套餐（菜品不支持更换/包含米饭x1）": "霸气嫩牛套餐",
            "【直播专享】椒麻鸡腿饭（例汤）": "椒麻鸡腿饭",
            "·六姐霸气嫩牛套餐（套餐菜品不支持更换）": "六姐霸气嫩牛套餐",
            "🌟🌟🌟五常稻花香米饭": "五常稻花香米饭",
            "福利加料 | 响铃卷【点💗收藏】": "响铃卷",
            "【尝鲜】武林香辣鸭头（半份5片)": "武林香辣鸭头",
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


if __name__ == "__main__":
    unittest.main()
