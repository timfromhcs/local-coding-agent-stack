# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability within this project:
1. Do NOT open a public issue.
2. Email details and reproduction steps to `timfromhcs@users.noreply.github.com`.
3. Provide reasonable time for remediation before any public disclosure.

## Security Practices in this Repository

- **Never Commit Secrets**: All API tokens, access credentials, and keys must remain in untracked local `.env` files.
- **Local Isolation**: The inference engine and proxy default to binding to `127.0.0.1` / `localhost` only. Do not expose unauthenticated proxy endpoints to public networks.
