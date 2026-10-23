# Security policy pack (starter)

Owner: <security lead>. Version: 0.1. Applies to every service in this repository.

### SEC-001 Check object-level authorisation on every read and write
Why: tenant data leaks come from endpoints that check the role but not the object's owner.
Check: each handler that loads a record by id compares its tenant or owner with the caller.
Example: `invoice = repo.get(id); authorize(caller, "read", invoice)`.

### SEC-002 Never log secrets, tokens or personal data
Why: logs are copied widely and kept for a long time.
Check: log calls do not include request bodies, headers named authorization or cookie, or fields
tagged as PII. Use the masking helper for identifiers.

### SEC-003 Parameterise every query and shell call
Why: string-built SQL and shell commands are the most common injection path.
Check: no string concatenation or f-strings in SQL, ORM `raw()` calls, or `subprocess` with
`shell=True` on input that a user can influence.

### SEC-004 Read secrets from the secret store at runtime
Why: secrets in code, config files or test fixtures end up in git history.
Check: no literal keys or passwords; configuration names the secret, not its value.

### SEC-005 Make payment-like actions idempotent
Why: retries and double clicks must not charge or refund twice.
Check: the handler takes an idempotency key and stores the result for replays.

### SEC-006 Justify every new dependency
Why: each package is code you now run in production.
Check: the spec names the package, why existing code cannot do the job, its licence, and that it
is maintained. Pin the version.
