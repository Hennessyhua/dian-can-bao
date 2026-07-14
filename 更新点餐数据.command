#!/bin/zsh
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

python3 scripts/update_site_data.py --scrape

echo
echo "更新完成。将改动提交并推送到 GitHub 后，网页会自动更新。"
read "REPLY?按回车关闭窗口…"
