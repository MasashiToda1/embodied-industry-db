.PHONY: lint lint-strict build test clean

# 默认门禁：stub 只警告不失败
lint:
	python3 scripts/lint.py --root .

# 发布前门禁：事件不足 3 条的主体也算失败
lint-strict:
	python3 scripts/lint.py --root . --strict

build:
	python3 scripts/compile.py --root . --out build

# 合规夹具必须通过并能编译，违规夹具必须被拒
test:
	@echo "=== 合规夹具 lint ==="
	@python3 scripts/lint.py --root tests/fixtures
	@echo "\n=== 合规夹具编译 ==="
	@python3 scripts/compile.py --root tests/fixtures --out tests/.build
	@echo "\n=== 违规夹具（预期失败）==="
	@if python3 scripts/lint.py --root tests/fixtures-bad > /dev/null 2>&1; then \
		echo "FAIL：违规夹具居然通过了门禁"; exit 1; \
	else \
		echo "OK：违规夹具被正确拒绝"; \
	fi

clean:
	rm -rf build tests/.build
