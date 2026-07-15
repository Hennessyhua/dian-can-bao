# 美团外卖订单爬取指南

> 点餐宝项目 · 数据采集 SSOT

## 原理

美团的消费者订单数据在桌面网页版没有入口，只能通过移动端 H5 页面访问。
核心流程：

1. 启动 Chrome 浏览器（带远程调试端口）
2. 访问 `h5.waimai.meituan.com` 移动端 H5 页面
3. 手机号 + 短信验证码登录
4. 通过浏览器内部 JavaScript 调用美团 API 拉取订单数据
5. 再调用订单详情 API 获取配送地址

## 前置条件

- macOS 系统（Chrome 浏览器）
- Python 3.10+
- `python3 -m pip install -r requirements.txt`
- 美团账号（手机号）

## 快速开始

### 方式一：一键脚本（推荐）

```bash
cd <点餐宝项目目录>
python3 scripts/update_site_data.py --scrape
```

脚本会自动：
1. 启动 Chrome（有头模式，可看到窗口）
2. 打开美团订单页
3. 通过 CDP 调用内部 API
4. 批量拉取所有订单及配送地址
5. 私有原始订单保存到 `.private/orders.raw.json`
6. 自动生成网页使用的脱敏数据 `web/public/data/orders.public.json`
7. 按订单上下文排除米饭、调料、口味、赠品、辅料和非餐饮产品
8. 为每道保留主菜推理 `breakfast` / `lunch` / `dinner`，并生成本地逐项审计文件

### 方式二：手动操作 + 半自动提取

如果希望手动登录（应对风控）：

```bash
# 1. 手动启动 Chrome
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9223 \
  --user-data-dir="$HOME/Library/Caches/cookie-cdp-chrome" \
  --window-size=430,932 \
  https://h5.waimai.meituan.com/waimai/mindex/olist

# 2. 在打开的窗口中手动登录
# 3. 登录后，在另一个终端运行提取脚本
python3 -c "
import json, requests
# ... (CDP连接提取代码)
"
```

## 数据字段说明

输出的 `orders.json` 每条包含：

| 字段 | 类型 | 说明 |
|:----|:----|:-----|
| orderId | string | 美团订单号 |
| restaurant | string | 餐厅名称（含分店） |
| items | array | 菜品列表 [{name, quantity}] |
| date | string | 下单日期 (YYYY-MM-DD) |
| time | string | 下单时间 (HH:MM) |
| total | number | 实付金额 |
| address | string | 配送地址 |
| receiver | string | 收货人 |
| phone | string | 收货人手机号 |

## 注意事项

1. **风控**：美团有 Yoda 风控系统，headless 模式会被拦截。必须使用有头模式 + 真实用户数据目录
2. **登录态**：Cookie 保存在 `cookie-cdp-chrome` 目录，可跨会话复用
3. **地址隐私**：脚本提取的地址仅进入本机 `.private/`；网页只接收「家（徐汇电影华苑）」或「新天地（徕卡办公室）」等地点标签，具体地址不得进入公开 JSON、页面、浏览器日志或前端缓存
4. **频率控制**：API 请求间隔 300ms，避免触发限流
5. **增量更新**：下次运行时脚本会自动去重，只新增未爬取的订单
6. **主菜粒度**：分类先使用现有历史条目的逐项审阅目录；新条目结合餐厅类型、同单主菜、份量描述与菜品语义进行上下文评分，不以单一关键词作为结论
7. **餐段归档**：早餐类菜品结合语义校正，其余菜品以历史下单时段的占优分布和中位小时推断

## 数据更新流程

```bash
# 每周/每月更新一次
cd <点餐宝项目目录>
python3 scripts/update_site_data.py --scrape
```

更新完成后，只需提交并推送脱敏文件和源码；GitHub Actions 会自动重新发布网页。原始订单目录已写入 `.gitignore`，不要使用 `git add -f` 强制提交。
