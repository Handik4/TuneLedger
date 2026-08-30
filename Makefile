.PHONY: test lint

test:
	.venv/bin/pytest contract/tests/ -v

lint:
	genvm-lint check contract/contracts/tuneledger_royalty.py
