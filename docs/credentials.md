# OpenRouter credential storage

On macOS, save the OpenRouter key in the local login Keychain. The private phone
handoff can perform this step before its declared work starts. Both Jev and text
inference reuse the same key during explicit executions; previews never read it.
The phone page states whether persistence is selected. Storage failure stops the
run rather than silently falling back to a transient credential or plaintext file.

## Set up on a Mac

Build once with the Python environment that will run inference (requires Apple's
command-line developer tools):

```sh
.venv/bin/python scripts/build_keychain.py
.venv/bin/python -m f1_pipeline.credentials store
.venv/bin/python -m f1_pipeline.credentials status
```

The store command prompts with hidden input. Do not put the key in command
arguments, chat, source, an env file or a receipt. A later `store` replaces the
same item. `status` reports item presence only, never the key or provider validity.
To remove this project's saved item:

```sh
.venv/bin/python -m f1_pipeline.credentials delete
```

The helper uses service `org.f1-content.openrouter` and account `openrouter` in
`~/Library/Keychains/login.keychain-db`. It uses Apple's native generic-password
APIs and the creator's default access control, without granting all applications
access. The key travels through process pipes; the public CLI has no print-key
operation. The fixed native helper can supply it to an executing local process.
This is encrypted storage at rest, not protection against compromised code running
as your logged-in user. It is the classic login Keychain, not iCloud sync or a
claim of device-only or screen-lock protection. A locked/denied Keychain fails
without an interactive unlock attempt. Rebuilding the helper may require renewed
macOS access approval because its executable identity changes.

An explicit `OPENROUTER_API_KEY` overrides Keychain. `F1_DISABLE_KEYCHAIN=1`
disables fallback. `scripts/check` sets that flag so normal offline verification
never accesses a real saved credential. The opt-in native integration test uses a
fresh UUID service, synthetic bytes and cleanup; it never touches production:

```sh
F1_KEYCHAIN_INTEGRATION=1 .venv/bin/python -m unittest discover -s tests -p test_credentials.py
```

The private phone Site temporarily encrypts the key for single-use pickup. Its
operator and Site credentials are separate from the OpenRouter key. The local
consumer checks the bound operation and storage choice, saves the key first and
then runs the declared plan. Neither the Site source nor event receipts contain
plaintext credentials.

## Execution limits

Plans support up to 64 declared jobs; text requests support 65,536 output tokens
and transport timeouts up to 300 seconds (CLI default 120). Provider limits still
apply. Budget must cover the sum of conservative job ceilings, and every run has
a fixed request/evidence hash and unique execution identity. Raising allowances
does not authorize automatic retries, provider fallback or purchases.

Sources: [Apple generic passwords](https://developer.apple.com/documentation/security/ksecclassgenericpassword),
[adding a Keychain password](https://developer.apple.com/documentation/security/adding-a-password-to-the-keychain),
and [OpenRouter reasoning-token allowance](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens).
