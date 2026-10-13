# Security Policy

## Reporting Security Issues

We take the security of **Self-Healing RAG Agent** seriously. If you discover a security vulnerability, please report it responsibly rather than opening a public issue on GitHub.

### Reporting Procedure
- **Email:** Send details to `security@selfhealingrag.local` or contact the repository maintainers privately.
- Include a description of the vulnerability, reproduction steps, and any proof of concept.
- Maintainers will acknowledge receipt within 48 hours and provide updates until resolution.

## Security Architecture & Best Practices

1. **Environment Variables & Secrets:**
   - All API keys, passwords, connection strings, and JWT secrets MUST be supplied through environment variables (`.env`).
   - `.env` is excluded from git tracking via `.gitignore`.
   - Never commit API keys or private tokens to public branches.

2. **Secret Redaction & Sanitization:**
   - The platform includes regex-based secret redaction in logging and telemetry pipelines (`KEY_REDACT_REGEX`), masking patterns such as `gsk_*`, `sk-*`, and HTTP `Bearer` tokens.
   - External connector credentials (GitHub tokens, database passwords) are masked upon retrieval and never sent unencrypted to the frontend.

3. **Authentication & Session Security:**
   - Passwords are encrypted using **Argon2id**.
   - Sessions utilize short-lived JWT access tokens and rotated refresh token families.
   - Token reuse detection revokes the entire token family upon duplicate presentation.
   - Demo Login (`DEMO_LOGIN_ENABLED`) is strictly disabled in production environments (`ENVIRONMENT=production`).

4. **Tenant Isolation & SQL Injection Protection:**
   - All database queries utilize SQLAlchemy 2.0 async parameterized queries or strict identifier validation (`SQL_IDENTIFIER_PATTERN`).
   - Multi-tenant data isolation ensures users can access only their own Knowledge Bases and documents.

## Accidental Credential Exposure Guidance
If a secret or credential was previously exposed or committed:
1. **Immediately revoke and rotate** the key at the provider dashboard (Groq, OpenAI, database host, etc.).
2. Do not assume deleting a commit or amending the latest commit erases Git history; purge the commit from repository history using `git-filter-repo` or BFG Repo-Cleaner before publishing.
