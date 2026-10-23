.PHONY: build lint test verify
build:
	@python3 -m compileall -q pricing.py
lint:
	@python3 -m py_compile pricing.py
test:
	@python3 -m unittest discover -s tests -t . -q
verify: build lint test
	@echo "verify: OK"
