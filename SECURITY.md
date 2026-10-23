# Security

This plugin controls a physical device through an unofficial cloud API. Review
the code before installing. Use a separate TCL Home account with only the
intended AC shared to it. Availability and compatibility are not guaranteed.

## Credentials

Setup stores a plaintext password in a user-owned mode-600 file outside the Git
checkout. This prevents other ordinary Linux users from reading it, not root,
malware, backups, or other processes/plugins running as your own user. Tokens
are not intentionally persisted. Do not publish your credential file, QR
invitations, tokens, raw API payloads, AWS credentials, or account/device IDs.

The companion socket is user-private and verifies the connecting UID. Commands
are allowlisted; it is not a general-purpose AWS proxy. Same-user processes can
still request controls: this is not an authorization boundary against your own
desktop applications.

## Reporting

For a suspected vulnerability, use this repository's GitHub **Security → Report
a vulnerability** feature. Do not post secrets in public issues. If that feature
is unavailable, open a minimal issue asking for a private reporting channel,
without vulnerability details or credentials. Rotate any accidentally exposed
passwords/tokens before discussing them.
