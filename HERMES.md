# Hermes 数据更新手册

Hermes 读取本仓库后，应使用统一入口更新点餐数据，不要直接编辑公开 JSON。

## 一键执行

- 只重新清洗本机现有原始订单：`./scripts/hermes_update_data.sh`
- 从美团抓取、合并并重新清洗：`./scripts/hermes_update_data.sh --scrape`

脚本会依次完成：原始订单合并、隐私地址映射、菜名清洗、独立主菜判断、同菜别名归并、早午晚餐及小吃分类、公开数据生成、单元测试、Python 编译检查和前端生产构建。任一步失败都必须停止，不得提交生成文件。

## 数据边界

- 私有原始数据：`.private/orders.raw.json`
- 私有分类审计：`.private/dish-classification.audit.json`
- 可发布数据：`web/public/data/orders.public.json`
- 菜品判断和同菜别名：`scripts/dish_intelligence.py`
- 抓取、合并和公开数据生成：`scripts/update_site_data.py`

`.private/` 中的文件不得提交 GitHub。公开数据中不得出现详细地址、收件人、电话、订单号、Cookie 或 Token。

## 新菜处理规则

1. 新商品先结合餐厅、同单其他商品、份量和完整菜名判断能否独立构成一餐。
2. 不能独立成餐的调料、米饭、口味、辅料、赠品、餐具、药品、日用品和非餐饮产品必须排除。
3. 新菜若与既有菜明确属于同一品类，在 `CURATED_DISH_ALIASES` 增加精确别名映射；禁止仅凭字符串相似度自动合并。
4. 若是新出现且需要永久保留或排除的历史商品，将精确名称加入对应的逐项审阅目录。
5. 修改规则后必须运行一键脚本，并审阅 `.private/dish-classification.audit.json` 中所有 `source: inferred` 的项目。

## 完成标准

- 全部单元测试通过。
- Vite 生产构建通过。
- 每个公开菜品都有唯一稳定的 `dishId` 和合法 `mealPeriod`。
- 同一 `dishId` 可以对应多次订单和多家分店，但随机推荐池只能生成一个候选。
- 公开数据隐私检查通过后，才允许提交和推送 GitHub。
