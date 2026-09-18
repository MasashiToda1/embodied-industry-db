.PHONY: lint lint-strict build test test-ingest preflight serve setup clean preview

# CI 里没有 .venv，用 PY=python3 覆盖
PY ?= .venv/bin/python

setup:
	uv venv --python 3.11
	uv pip install pyyaml fastapi uvicorn httpx beautifulsoup4 lxml

# 入库后台：粘 URL 或整页 HTML，解析存快照，审过才写 events/
serve:
	$(PY) -m ingest.server

# 默认门禁：stub 只警告不失败
lint:
	$(PY) scripts/lint.py --root .

# 发布前门禁：事件不足 3 条的主体也算失败
lint-strict:
	$(PY) scripts/lint.py --root . --strict

build:
	$(PY) scripts/compile.py --root . --out build

# 看某个主体编译后长什么样。PR 里附这个比附 YAML 直观：
# 能直接看出这条事件把时间线和技术栈变成了什么样。
#   make preview ORG=unitree
preview: build
	@cat build/orgs/$(ORG).md

# 合规夹具必须通过并能编译，违规夹具必须被拒
test:
	@echo "=== 合规夹具 lint ==="
	@$(PY) scripts/lint.py --root tests/fixtures
	@echo "\n=== 合规夹具编译 ==="
	@$(PY) scripts/compile.py --root tests/fixtures --out tests/.build
	@echo "\n=== 违规夹具（预期失败）==="
	@if $(PY) scripts/lint.py --root tests/fixtures-bad > /dev/null 2>&1; then \
		echo "FAIL：违规夹具居然通过了门禁"; exit 1; \
	else \
		echo "OK：违规夹具被正确拒绝"; \
	fi

test-ingest:
	$(PY) tests/test_wechat.py
	@echo
	$(PY) tests/test_tender.py
	@echo
	$(PY) tests/test_paper.py

# 推送前跑这一条。但它不能替代 PR 上的 Actions——
# 本地环境和 CI 不一定一致，最终以 PR Checks 为准。
preflight: lint test test-ingest build
	@echo "\n▸ preflight 全部通过，可以推送"

clean:
	rm -rf build tests/.build
