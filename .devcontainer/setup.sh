#!/usr/bin/env bash
# Codespace 创建时跑一次：装 uv、建 venv、装依赖、自检。
set -euo pipefail

echo "▸ 安装 uv"
curl -fsSL https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
# 之后开终端也能直接用 uv
grep -q 'HOME/.local/bin' ~/.bashrc 2>/dev/null || \
  echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc

echo "▸ 建 venv 并装依赖"
uv venv --python 3.11
uv pip install pyyaml fastapi uvicorn httpx beautifulsoup4 lxml

echo "▸ 自检"
.venv/bin/python scripts/lint.py --root . || true
make test-ingest

cat <<'EOF'

────────────────────────────────────────────
具身产业库已就绪。

  make serve     起入库后台，右下角弹出的地址点开就是界面
  make lint      门禁
  make build     编译主体页到 build/

投完料记得提交：
  git add -A && git commit -m "入库：..." && git push

────────────────────────────────────────────
EOF
