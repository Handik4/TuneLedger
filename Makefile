.PHONY: test lint

test:
	.venv/bin/pytest packages/tests/ -v

lint:
	genvm-lint check packages/contracts/tuneledger_royalty.py
