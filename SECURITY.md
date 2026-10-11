# Security

This is an alpha local research tool. Use the latest reviewed `main` revision;
there is no maintained older release series or security response SLA yet.

Do not put keys, browser cookies, signed source URLs, unpublished footage or local
account details in issues, pull requests or test fixtures. In this checkout, the
direct Jev client reads `TYPESAFE_API_KEY` and hosted text execution reads
`OPENROUTER_API_KEY` from the invoking process. Preflight and offline tests need
neither. The [mobile handoff](docs/mobile-review.md#supply-an-openrouter-key-from-a-phone)
uses separate runtime secrets and encrypted, single-use pickup. The explicit
[live feed](docs/live-feed.md) uses saved Codex ChatGPT authentication and refuses
API-key fallback. Keep credentials and private receipts outside source control.
Newer `main` adds consent-bound Keychain storage; see [project state](docs/project-state.md)
before assuming those commands exist here. Rotate an exposed credential; deleting
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
