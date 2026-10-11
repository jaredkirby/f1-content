# Security

This is an alpha local research tool. Use the latest reviewed `main` revision;
there is no maintained older release series or security response SLA yet.

Do not put keys, browser cookies, signed source URLs, unpublished footage or local
account details in issues, pull requests or test fixtures. The optional Jev client
reads `TYPESAFE_API_KEY` only from its process environment. Offline tests do not
need credentials. Rotate a credential if it is exposed; deleting its file does
not remove it from Git history.

For a vulnerability, use the repository's **Security → Report a vulnerability**
when private reporting is enabled on its eventual hosting service. If that option
is unavailable, ask a maintainer for a private reporting channel without posting
exploit details or secrets. This local repository does not yet have a hosted
security inbox. Maintainers should enable private vulnerability reporting before
inviting public contributions.

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
