# Security

This is an alpha local research tool. Use the latest reviewed `main` revision;
there is no maintained older release series or security response SLA yet.

Do not put keys, browser cookies, signed source URLs, unpublished footage or local
account details in issues, pull requests or test fixtures. In this checkout, the
legacy direct Jev client reads `TYPESAFE_API_KEY`. OpenRouter Jev/text execution
uses `OPENROUTER_API_KEY` or consent-bound [login-Keychain storage](docs/credentials.md). Preflight and offline tests need
neither. The [mobile handoff](docs/mobile-review.md#supply-an-openrouter-key-from-a-phone)
uses separate runtime secrets and encrypted, single-use pickup. The explicit
[live feed](docs/live-feed.md) uses saved Codex ChatGPT authentication and refuses
API-key fallback. Keep credentials and private receipts outside source control.
The [project state](docs/project-state.md) describes the combined implementation. Rotate an exposed credential; deleting
its file does not remove it from Git history.

For a vulnerability, use the repository's **Security → Report a vulnerability**
on GitHub if private reporting is enabled. Its availability was not checked in
this review. If the option is unavailable, ask a maintainer for a private reporting
channel without posting exploit details or secrets. Maintainers should verify
private vulnerability reporting before inviting public contributions.

Reports should include the affected revision, impact and a minimal synthetic
reproduction. Treat downloaded pages, filenames, captions and model output as
untrusted input. Keep the workspace sandbox and normal approvals enabled. Do not
run untrusted public pull requests on the production media computer; CI uses
ephemeral hosted runners and read-only repository permissions.

`scripts/repo_guard.py` detects common accidental publication patterns in Git's
index. It is not a complete secret scanner, media-rights audit or sandbox.
The README and committed workflow guide have a narrow, reviewed exception for
their exact private Site homepage links. It does not allow credentials, signed
URLs, private URL paths/queries or those addresses in other files; the Sites
retain their owner-only access controls.
