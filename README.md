# 🍽️ 点餐宝 — 解决选择困难症

一键解决「今天吃什么」的千古难题。

## 数据来源

从你的美团外卖历史订单中爬取的真实数据。
- 时间跨度：2025-11 ~ 2026-07（8个月）
- 订单数：158 条
- 餐厅数：75 家
- 菜品数：185+ 道
- 总消费：¥6,076.12
- 前端地点标签：家（徐汇电影华苑）/ 新天地（徕卡办公室）
- 隐私规则：前端及公开文件不展示具体收件地址

## 功能

- 🎲 **随机选餐**：从归档后的独立主菜中随机，交给命运
- 🕐 **餐段筛选**：按历史下单时间与菜品语义推理早饭 / 午饭 / 晚饭
- 📍 **按地点筛选**：家 / 新天地
- 🏷️ **更多筛选**：菜系、餐厅、最近点过
- 📊 **数据看板**：最常吃的店、最爱的菜、月度账单
- 🔒 **地址别名**：本地更新脚本将收件地址映射为地点标签，公开网页不接触具体地址
- 📱 **简洁前端**：移动端优先，核心流程只保留“选餐段 → 选地点 → 换一个”
- 🌐 **GitHub Pages**：静态部署，不需要云服务器

## 项目结构

```
点餐宝/
├── .github/workflows/       # GitHub Pages 自动发布
├── .private/                # 私有原始数据（自动忽略，不上传）
├── data/
│   └── orders.json          # 旧版私有原始订单（已加入 .gitignore）
├── scripts/
│   └── meituan_scraper.py   # 美团订单爬取脚本
│   └── update_site_data.py  # 采集、地点映射、脱敏与公开数据生成
│   └── dish_intelligence.py # 主菜归档、上下文推理与餐段分类
│   └── hermes_update_data.sh# Hermes 一键更新、验证与构建入口
├── web/                     # React + Vite 静态网页
│   ├── src/
│   └── public/data/         # 可公开的脱敏订单
├── docs/
│   ├── SCRAPING_GUIDE.md    # 爬取指南
│   └── PRD.md               # 产品需求文档
├── requirements.txt
└── README.md
```

## 首次安装

```bash
cd <点餐宝项目目录>
python3 -m pip install -r requirements.txt
cd web && npm install
```

## 随时更新美团数据

```bash
cd <点餐宝项目目录>
python3 scripts/update_site_data.py --scrape
```

该命令会：打开美团登录页、采集订单、将原始数据保存在 `.private/`、把地址映射为地点标签、清除菜名营销内容、逐项归档独立主菜及小吃、推理早午晚餐段，并生成 `web/public/data/orders.public.json`。逐项审计结果保存在 `.private/dish-classification.audit.json`。提交并推送公开文件后，GitHub Pages 会自动更新。

只想根据本机已有订单重新生成网页数据时：

```bash
python3 scripts/update_site_data.py
```

Hermes 读取仓库后应先查看 `HERMES.md`，并使用统一入口：

```bash
./scripts/hermes_update_data.sh --scrape  # 抓取新订单并清洗
./scripts/hermes_update_data.sh           # 仅重新清洗本机数据
```

该入口还会完成同菜去重、单元测试、Python 编译检查和前端生产构建；任一步失败都会停止。

## 本地预览

```bash
cd web
npm run dev
```

## GitHub Pages 发布

1. 将项目推送到 GitHub 的 `main` 分支。
2. 在仓库 Settings → Pages 中，将 Source 设为 **GitHub Actions**。
3. 此后每次推送，`.github/workflows/pages.yml` 会自动构建和发布 `web/dist`。

> GitHub Pages 上的脱敏订单仍是公开数据，会包含餐厅、菜品、日期、金额和地点标签，但绝不包含订单号、姓名、电话或具体地址。

## 开发计划

见 `docs/PRD.md`
