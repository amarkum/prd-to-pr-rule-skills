.PHONY: test validate demo evals pdf details

test:            ## unit tests: scripts, hooks, onboarding CLI, manifest consistency (stdlib + PyYAML)
	python3 -m unittest discover -s tests

validate:        ## strict validation of the marketplace and every plugin (needs the claude CLI)
	claude plugin validate --strict .
	for p in plugins/*/; do claude plugin validate --strict $$p || exit 1; done

details:         ## component inventory and always-on token cost per plugin
	for p in plugins/*/; do claude --plugin-dir $$p plugin details $$(basename $$p); done

demo:            ## deterministic end-to-end demo (PRD gate, AC coverage, fail-to-pass evidence, PR gate)
	python3 examples/demo.py

evals:           ## behavioural evals with real model runs (costs money; Linux needs bubblewrap + socat)
	cd plugins/sdlc-core && claude plugin eval . --trust-plugin --scaffold --allow-tools Bash Edit Write --runs 3 --threshold 0.8 --no-publish --max-cost-usd 10

pdf:             ## render docs/playbook.html to docs/playbook.pdf (needs Node + Playwright)
	node docs/build-pdf.cjs
