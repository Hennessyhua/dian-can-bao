#!/usr/bin/env python3
"""订单级菜品归档与餐段推理。

现有历史条目优先走人工审阅后的精确目录；未来出现的新条目，会综合餐厅类型、
同单主菜、份量描述和菜品语义评分，而不是依赖单个关键词直接分类。
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from statistics import median
from typing import Any


CLASSIFICATION_VERSION = 3
MEAL_PERIODS = ("breakfast", "lunch", "dinner")

# 经历史订单、餐厅与商品结构逐项核对后确认的同菜别名。这里只接受明确别名，
# 不用字符串相似度自动合并，避免把“酸汤肥牛米粉”和“酸汤肥牛套餐”等误归为一类。
CURATED_DISH_ALIASES = {
    "六姐霸气嫩牛套餐": "霸气嫩牛套餐",
    "夫妻肺片单人饭套餐": "夫妻肺片套餐",
    "满碗是料·宜宾燃面": "宜宾燃面",
    "鲜滑嫩牛肉套餐+主食自选/包含口味": "鲜滑嫩牛肉套餐+主食自选",
    "小炒黄牛肉 盖码饭": "小炒黄牛肉盖码饭",
    "香辣大鸡排": "正新香辣大鸡排",
}

# 逐项审阅后确认：这些条目不能独立构成一餐。
CURATED_EXCLUDED_NAMES = frozenset({
    # 2026-07 双账号合库时逐项复核：饮品、甜点、水果、餐具、加料与同单配菜。
    "0脂脆波波",
    "Amazing",
    "一次性餐具包",
    "三丁纸皮烧麦1个",
    "不需要餐具",
    "云南花香蓝莓 125g/盒",
    "五香茶叶蛋",
    "免费茶叶蛋一个",
    "凤梨夹乌梅约250克",
    "凤梨果切.150g",
    "剥壳荔枝+芒果+西瓜.350g",
    "加工馕",
    "加辣",
    "午餐肉",
    "双拼鸡蛋仔",
    "和府餐具包",
    "大口吃芒果果切约200克",
    "大师溏心蛋",
    "小串冰糖葫芦5串任选",
    "小白甜豆浆",
    "小青菜",
    "年糕片",
    "当季双拼自选果切约220克",
    "必喝系列5选2",
    "抹茶米麻薯流心挞",
    "整块芒果糯米糍",
    "新鲜凤梨果切约250克",
    "无需保温袋",
    "暖宝宝暖贴·宫小燕品牌",
    "曼谷日落·咸法酪泰奶",
    "杨桃三重甘",
    "杨梅百香观音",
    "洗净美早樱桃+凤梨果切约220克",
    "炸泡菜饺子 튀긴만두",
    "炸淀粉肠",
    "炸烤馕",
    "炸馕",
    "炸骨肉相连",
    "炸鱼排",
    "炸鱼豆腐",
    "牛肉丸",
    "特价福利素食",
    "特价豆浆一袋",
    "狼牙土豆条",
    "环保餐具",
    "现烤玫瑰鲜花饼",
    "白灼生菜",
    "空运云南黑炭杨梅约250克",
    "米饭",
    "红枣牛奶/椰奶炖桃胶300ml",
    "红集乌梅凤梨.250g",
    "红集品牌西瓜果切.250-500g",
    "缤纷综合果仁·宫小燕品牌",
    "肉粉松",
    "自选水果桶约400克",
    "草莓+凤梨乌梅+乌梅小番茄.350g",
    "草莓奶酪糯米糍",
    "蜂巢焦糖鲜牛乳茶",
    "赣南橙子鲜切.250g",
    "酒酿芝麻汤圆",
    "醪糟黑芝麻汤圆",
    "里脊肉",
    "金砖丝袜奶茶 ❥→连冰块都是用奶茶做的",
    "针王蜜瓜",
    "铁板手撕包菜",
    "锁鲜卤鸭脖",
    "随心自选双拼果切.250",
    "餐具",
    "餐具包",
    "鱼豆腐",
    "鲜椒土豆丝",
    "鸡腿肉",
    "黄金小馒头4个",
    "黄金薯塔",
    "💥吃面必备3选1",
    "一次性餐具",
    "不需要环保包装袋",
    "11枝红玫瑰鲜花花束送女友爱人表白恋人生日送花花店送花上门",
    "BHC同款芝士球1颗",
    "CERAVE适乐肤 神经酰胺屏障修护润肤乳身体乳 30ml多规格旅行装小样试用装",
    "LA ROCHE-POSAY理肤泉B5多效保湿修护面膜25g/片 旅行装小样",
    "乌梅凤梨+乌梅番茄",
    "五常大米",
    "五常稻花香米饭",
    "伍德氏灯 UV紫光灯 USB充电式照猫藓猫癣灯防伪验钞玉石检测宠物真菌检测手电筒黑色/个",
    "优质餐具包",
    "六姐牛油",
    "六姐麻辣",
    "军屯锅盔",
    "加一个荷包蛋",
    "单人套餐",
    "单人自选套餐",
    "口腔溃疡膜Φ1.2cm*12片/盒辅助治疗口腔溃疡贴",
    "响铃卷",
    "土豆丝",
    "复方氨酚烷胺胶囊8粒*2板/盒",
    "感冒灵颗粒10g*9袋/盒",
    "奇兰芭乐莲雾",
    "套餐",
    "奶白菜",
    "威宁洋芋粑",
    "娃娃菜",
    "嫩牛肉",
    "小型犬专用狗厕所防踩屎 易清理抽屉式狗厕所 狗狗厕所1个",
    "小白豆浆",
    "小米南瓜粥",
    "开胃小菜",
    "强力真空马桶吸盘 1个 马桶疏通器管道疏通器家用厕所泵下水道皮吸子",
    "微辣",
    "快活煎蛋",
    "手工现炸油条",
    "手工钢锯家用木工钢锯架重型钢锯架可调节钢锯架12寸锯弓／把",
    "招牌软糯耙鸡爪/1只",
    "收藏zeng送",
    "收藏点亮丨秘制香辣蘸料~仅限一份喔",
    "斑斓青团",
    "方便面",
    "无矾大油条",
    "柚子芒果船·固体杨枝甘露约250-300克",
    "正宗潮汕牛筋丸1颗",
    "武林香辣鸭头",
    "水果夹干噎酸奶黄肉菠萝蜜250克",
    "泰奶冰淇淋茶",
    "泰椒土豆丝",
    "清炒空心菜",
    "烤豆角串",
    "烤辣椒串",
    "烤鱼豆腐",
    "烫时令蔬菜",
    "爆汁炸鸡块",
    "牛奶复原乳245ml",
    "特价1元购红豆稀饭",
    "特价菜品3选1一份",
    "玉米糁米饭",
    "现炖鲜鸡丝汤",
    "生菜",
    "毓婷 验孕棒3盒 人绒毛膜促性腺检测试纸胶体金法纸早早孕验孕棒验孕时值",
    "白米粥",
    "秘制酱汁",
    "网红淀粉肠",
    "网红炸蛋",
    "老板疯了！蔬菜鸡肉饼",
    "肥牛卷",
    "肥牛片",
    "船盒",
    "英国普乐高宁犬猫屎肠球菌止泻调理肠胃腹泻呕吐15ml",
    "绿联 手机防水袋可触屏防水袋游泳漂流挂脖手机套适用苹果安卓7.2英寸",
    "茶叶蛋",
    "茶叶蛋1个",
    "苕皮包肉沫",
    "苕皮包里脊肉",
    "莲藕排骨汤",
    "蒜香小排",
    "虾滑",
    "西瓜啵啵",
    "豆干包里脊肉",
    "豌豆尖",
    "贵州秘制泡菜和黄金豆双拼嗦粉灵魂伴侣",
    "贵州酸汤锅底",
    "软糯年糕",
    "辣椒干碟",
    "辣翅买一送一",
    "避风塘大虾塔可",
    "酒酿红豆豆花冻+古法桂花酒酿",
    "酥香嫩鱼块",
    "酸脆爽口解腻萝卜.",
    "醋酸地塞米松口腔贴片0.3mg*10片/板/盒",
    "金针菇",
    "需要餐具",
    "阿莫西林胶囊0.25g*30粒/盒",
    "零度可乐",
    "韩式炸无骨鸡块2块",
    "韩式萝卜片",
    "飞科高速电吹风机负离子养发6371灰",
    "香脆牛肉饼",
    "香菜",
    "马桶疏通器捅厕所下水道清洁棒堵塞神器高压吸家用管道一炮通工具 1/套",
    "鸡脚筋",
    "麻辣香辣",
    "黄金炸蛋",
})

# 容易被通用规则误判、但经订单上下文审阅后可以独立成餐的条目。
CURATED_INCLUDED_NAMES = frozenset({
    # 2026-07 双账号合库时逐单复核：以下商品可作为一次独立餐食推荐。
    "三拼炸鸡～多种口味一次满足", "三鲜蒸饺", "两荤两素任你选+2荤2素自选",
    "丰富有料套餐", "乌香黑米粥", "五花肉炒芸豆丝盖码饭",
    "元气黑芝麻香蕉三明治", "充能版 • 谷物碗", "全麦牛油果草鸡蛋三明治",
    "兰州牛肉拌面", "凉皮+肉夹馍/堡+黑胡椒鸡块3块+饮品", "双人随心选",
    "双拼瓦香排骨+瓦香鸡+配菜+米饭", "大份黄焖鸡+10任选3配菜+香米饭",
    "大口过瘾红烧牛肉刀削汤面", "大王锅贴二两", "嫩牛肉肉酱米线+煎蛋/炸蛋",
    "宫爆鸡丁盖饭", "小炒鲜仔鸡单人餐", "小炒黄牛肉 盖码饭", "小炒黄牛肉盖码饭",
    "恰巴塔板烧鸡腿堡", "泰式打抛猪肉饭", "招牌火车头河粉", "招牌里脊肉炒饭",
    "排骨凤爪饭", "揪片子汤饭", "牛腩笋尖双拼粉", "新疆炒米粉",
    "无骨炸鸡&年糕套餐", "杂粮煎饼➕鸡蛋➕土豆丝➕里脊肉➕生菜",
    "柚子鸡汤关东煮Chicken Soup", "正新香辣大鸡排", "香辣大鸡排",
    "法香鸡腿烤蔬能量碗", "泰式炒金边粉", "海苔酥脆松包饭 김맛육송",
    "炭烧牛腹肉茶泡饭", "烤牛肉/辣炒猪肉双拼紫菜包饭소고기/돼지",
    "烤牛肉丁包饭 달달소고기", "牛腩拼笋尖米粉", "玉米粒沙拉包饭 콘마요",
    "疆咖拌米粉", "碳烤照烧鸡包饭 치킨데리야끼", "罗田板栗烧鸡",
    "肥牛烫捞7荤7素+小吃自选3件套", "肥牛酸辣汤面", "肯德基天府椒麻香辣粉",
    "自搭双人餐", "荠菜鲜肉馄饨", "葱油鸡扒脆边蛋饭", "藕巷牛腩粉",
    "豆芽粉丝小笼包", "辣炒猪肉包饭 매운제육볶음", "酱 香 鸡 肉 炒 米 粉",
    "酱香鸡炒米粉宽粉", "酱香鸡肉炒米粉", "酸奶碗diy2水果+2小料",
    "酸汤臊子面", "酸菜酸汤臊子面", "酸辣手撕鸡+素菜+米饭",
    "里脊肉手抓蛋饼", "韭菜盒子", "馕芹菜鸡肉炒米粉", "鱼香肉丝盖饭",
    "鲜虾云吞港式汤面一人食", "鸡蛋饼+土豆丝+香肠", "분모자떡볶이 韩式炒年糕",
    "20选5单人自选套餐", "9秒爆鲜牛肉", "亚麻籽油烤虾超级碗套餐",
    "全家福小笼包", "全家福麻团乌饭+豆浆", "六姐霸气嫩牛套餐",
    "堡卷随心选3件套", "夫妻肺片单人饭套餐", "夫妻肺片套餐",
    "双人自选帕尼尼+三明治", "安又胖韩式冷面单人餐", "宜宾燃面",
    "小杨生煎", "小杨锅贴单人餐", "小杨饱饱餐",
    "干切牛肉汤类+牛肉锅贴1两", "干锅牛蛙单人套餐+主食自选",
    "干锅麻辣牛肉拌粉", "怂厂随心搭+奶茶自选豪华套餐",
    "手打鲜虾滑单人餐", "招牌尖椒炒仔鸡", "招牌打抛饭配流心蛋",
    "招牌红烧牛腩任意双拼套餐", "招牌遵义羊肉粉👍", "招牌酱香牛腱子铜锅米线",
    "排骨凤爪饭套餐", "新春汉堡随心拼", "更香更辣鸡腿堡4件套",
    "杂粮饼十蛋十脆饼十烤肠十里脊十辣条", "椒麻鸡腿饭", "楚留香碎碎鸡",
    "油豆腐牛肉粉丝汤", "泰椒土豆丝+峨眉老豆花+米饭", "活鱼烤鱼一人食-含米饭",
    "满碗是料·宜宾燃面", "炸肉酱拼60克吊龙米线", "热辣双拼炸鸡任选2件",
    "牛肉抄手", "牛肉燃面", "猪头肉+素菜+米饭", "现蒸鲜肉小笼包7个＋慢熬南瓜粥",
    "盐菜回锅肉单人套餐", "砂锅芸豆+鲜牛肉+米饭+可乐", "秘制猪头肉拼肠套餐",
    "秘制鸡腿肉单人套餐+主食自选/包含口味", "笋子牛肉米粉", "网红小笼包麻辣味",
    "老手艺炸肉酱米线+小吃自选5选1", "老贵阳辣鸡粉", "老麻抄手",
    "脆哨炒饭", "自选粥品+香辣肉夹馍", "花溪牛肉粉+酸萝卜+荷包蛋",
    "豆花牛肉",
    "豪大鸡排2人套餐", "辣皮子肥牛生煎", "酸汤肥牛+素菜+米饭",
    "酸汤肥牛米粉", "里脊肉甜辣手抓蛋饼3件套", "里脊肉葱抓蛋饼4件套单人餐",
    "金沙咸蛋黄嫩鸡比萨", "霸气嫩牛套餐", "青菜玉米粥", "青菜瘦肉粥",
    "马德里风情牛腩大虾比萨", "鲜嫩牛肉扁粉",
    "鲜椒土豆丝+米饭1份", "鲜滑嫩牛肉套餐+主食自选",
    "鲜滑嫩牛肉套餐+主食自选/包含口味", "鲜肉小笼包", "麻辣牛肉酱拌面",
    "麻麻辣辣牛肉饭", "藕汤烫饭", "虾仁扬州蛋炒饭", "虾兵蟹将套餐B",
})

BREAKFAST_OVERRIDES = frozenset({
    "全家福小笼包", "全家福麻团乌饭+豆浆", "双人自选帕尼尼+三明治",
    "小米南瓜粥", "干切牛肉汤类+牛肉锅贴1两",
    "杂粮饼十蛋十脆饼十烤肠十里脊十辣条", "现蒸鲜肉小笼包7个＋慢熬南瓜粥",
    "里脊肉甜辣手抓蛋饼3件套", "里脊肉葱抓蛋饼4件套单人餐",
    "鲜嫩牛肉扁粉", "鲜肉小笼包",
})

NON_MEAL_RESTAURANT_PATTERN = re.compile(
    r"药房|快药|医疗器械|宠医|宠物|超市|旗舰店|鲜花店|HARMAY|話梅",
    re.IGNORECASE,
)
MAIN_DISH_PATTERN = re.compile(
    r"套餐|单人餐|双人|饭|面|粉|粥|包|饼|锅贴|抄手|米线|烤鱼|比萨|披萨|汉堡|"
    r"牛蛙|炒仔鸡|牛肉|鸡腿|虾仁|汤类|生煎|随心拼|随心搭|超级碗",
    re.IGNORECASE,
)
AUXILIARY_PATTERN = re.compile(
    r"口味|蘸料|酱汁|干碟|锅底|赠送|收藏|加一个|米饭|大米|蔬菜|生菜|香菜|"
    r"可乐|豆浆|茶叶蛋|荷包蛋|船盒|微辣|麻辣香辣|1颗|1只|一份喔|\d+g",
    re.IGNORECASE,
)


def observed_period(time_value: str) -> str:
    try:
        hour = int(str(time_value or "").split(":", 1)[0])
    except (TypeError, ValueError):
        return "dinner"
    if 5 <= hour < 10:
        return "breakfast"
    if 10 <= hour < 15:
        return "lunch"
    return "dinner"


def canonicalize_dish_name(name: str) -> tuple[str, str]:
    """返回稳定品类名与归并依据；仅合并已确认的同菜别名。"""
    canonical = CURATED_DISH_ALIASES.get(name, name)
    if canonical != name:
        return canonical, "逐项审阅别名：跨时间或分店视为同一菜品"
    return canonical, "清洗后名称一致：跨订单直接归并"


def classify_item_role(name: str, restaurant: str, sibling_names: list[str]) -> tuple[bool, str, str]:
    """返回 (是否主菜, 来源, 原因)。"""
    if name in CURATED_EXCLUDED_NAMES:
        return False, "curated", "历史条目逐项审阅：附属项、非正餐或非餐饮产品"
    if name in CURATED_INCLUDED_NAMES:
        return True, "curated", "历史条目逐项审阅：可独立构成一餐"
    if NON_MEAL_RESTAURANT_PATTERN.search(restaurant):
        return False, "context", "餐厅类型不是餐饮门店"

    main_score = 0
    auxiliary_score = 0
    if len(sibling_names) == 1:
        main_score += 3
    if MAIN_DISH_PATTERN.search(name):
        main_score += 4
    if len(name) >= 6:
        main_score += 1
    if AUXILIARY_PATTERN.search(name):
        auxiliary_score += 4
    if len(name) <= 4 and len(sibling_names) > 1:
        auxiliary_score += 2
    stronger_sibling = any(
        sibling != name and MAIN_DISH_PATTERN.search(sibling) and not AUXILIARY_PATTERN.search(sibling)
        for sibling in sibling_names
    )
    if stronger_sibling:
        auxiliary_score += 2

    keep = main_score > auxiliary_score and main_score >= 3
    reason = f"上下文评分：主菜{main_score}，附属{auxiliary_score}，同单{len(sibling_names)}项"
    return keep, "inferred", reason


def infer_meal_period(name: str, observations: list[dict[str, str]]) -> tuple[str, str]:
    if name in BREAKFAST_OVERRIDES:
        return "breakfast", "菜品语义与历史时间共同确认早餐"

    periods = [observed_period(item.get("time", "")) for item in observations]
    counts = Counter(periods)
    if counts:
        top_count = max(counts.values())
        tied = [period for period in MEAL_PERIODS if counts[period] == top_count]
        if len(tied) == 1:
            return tied[0], f"历史下单时段占优：{dict(counts)}"

    hours = []
    for item in observations:
        try:
            hours.append(int(str(item.get("time") or "").split(":", 1)[0]))
        except (TypeError, ValueError):
            continue
    middle = median(hours) if hours else 18
    if middle < 10:
        period = "breakfast"
    elif middle < 15:
        period = "lunch"
    else:
        period = "dinner"
    return period, f"时段并列，按历史中位下单小时 {middle:g} 推断"


def archive_orders(orders: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """过滤附属项、归并同菜别名、建立稳定餐段，并返回可审计结果。"""
    role_audit: dict[str, dict[str, Any]] = {}
    observations: dict[str, list[dict[str, str]]] = defaultdict(list)
    provisional: list[dict[str, Any]] = []

    for order in orders:
        sibling_names = [str(item.get("name") or "") for item in order.get("items") or []]
        kept_items = []
        for item in order.get("items") or []:
            name = str(item.get("name") or "")
            keep, source, reason = classify_item_role(name, str(order.get("restaurant") or ""), sibling_names)
            audit = role_audit.setdefault(name, {
                "name": name, "keep": keep, "source": source, "reason": reason,
                "occurrences": 0, "restaurants": set(), "times": [],
            })
            audit["occurrences"] += int(item.get("quantity") or 1)
            audit["restaurants"].add(str(order.get("restaurant") or ""))
            if order.get("time"):
                audit["times"].append(str(order["time"]))
            if keep:
                canonical_name, canonical_reason = canonicalize_dish_name(name)
                audit["canonicalName"] = canonical_name
                audit["canonicalReason"] = canonical_reason
                kept_items.append({**item, "name": canonical_name})
                observations[canonical_name].append({"time": str(order.get("time") or "")})
        if kept_items:
            merged_items: dict[str, dict[str, Any]] = {}
            for item in kept_items:
                existing = merged_items.setdefault(item["name"], {**item, "quantity": 0})
                existing["quantity"] += int(item.get("quantity") or 1)
            provisional.append({**order, "items": list(merged_items.values())})

    meal_periods = {name: infer_meal_period(name, seen) for name, seen in observations.items()}
    archived = []
    for order in provisional:
        items = []
        for item in order["items"]:
            period, _ = meal_periods[item["name"]]
            items.append({**item, "mealPeriod": period})
        archived.append({**order, "items": items})

    audit_rows = []
    for name in sorted(role_audit):
        row = role_audit[name]
        period, period_reason = meal_periods.get(name, (None, None))
        audit_rows.append({
            **{key: value for key, value in row.items() if key != "restaurants"},
            "restaurants": sorted(row["restaurants"]),
            "mealPeriod": period,
            "mealPeriodReason": period_reason,
        })

    return archived, {
        "classificationVersion": CLASSIFICATION_VERSION,
        "uniqueSourceItems": len(role_audit),
        "uniqueKeptSourceItems": sum(1 for row in audit_rows if row["keep"]),
        "uniqueMealItems": len(meal_periods),
        "uniqueExcludedItems": sum(1 for row in audit_rows if not row["keep"]),
        "items": audit_rows,
    }
