# Security Policy

## Multi-user isolation

This fork adds user-level data isolation via HMAC-signed identity cookies. Each
user gets a random `owner_id` that scopes their tasks, gallery items, and
reference assets. All API endpoints, SSE events, and image routes enforce
ownership checks.

**Critical**: The `WEBUI_OWNER_SECRET` environment variable signs identity
cookies. If it changes (or is left as the default random value), all users lose
their sessions on restart. For multi-user deployments, generate a fixed value:

```bash
openssl rand -hex 32
```

If the secret is lost, users can recover their data via the `key_hash` recovery
anchor (browser-fingerprint-based), but this is not guaranteed across browser
updates.

## BYOK key handling

BYOK (Bring Your Own Key) API keys are:

1. Stored only in the user's browser `localStorage`.
2. Sent with each form submission as transient form data.
3. Held in server memory (`ctx.byok_keys[task_id]`) only during task execution.
4. **Never** written to the task database, params JSON, or logs.

A CLI tool (`strip_byok_keys.py`) is provided to purge any BYOK keys that older
versions may have persisted in historical task params.

## Local data and secrets

Do not publish OAuth tokens, API keys, account files, `.env` files, input images,
generated outputs, task metadata, SQLite databases, or debug logs.

Sensitive local paths include:

- `~/.codex/auth.json`
- `output/`
- `outputs/`
- `input/`
- `inputs/`
- `data/` (Docker volume mount)
- `.env` (Docker environment file)

## Advanced local auth warning

The optional Codex / ChatGPT OAuth mode calls an internal ChatGPT backend
endpoint. It is not an officially recommended OpenAI API integration path and
may change or stop working without notice. Prefer OpenAI-compatible API mode or
BYOK mode for stable integrations.

## Public share gallery

The `/explore` page exposes publicly shared tasks. Only the following fields are
included in share responses:

- `share_id` (not the raw task_id)
- `prompt`, `safe_parameters`, `output_urls`, `thumb_urls`
- `shared_at`, `shared_by` (anonymized `public_author_id`), `share_note`

API keys, owner IDs, internal task metadata, and file paths are never exposed.
Shared images use a 5-minute cache (`Cache-Control: public, max-age=300`); if a
share is revoked, the image may remain accessible for up to 5 minutes.

## Docker deployment notes

When deploying via Docker:

- Set `WEBUI_OWNER_SECRET` to a fixed random value.
- Consider setting `WEBUI_DISABLE_DELETION=1` to prevent users from deleting
  each other's tasks in shared deployments.
- The `./data` volume contains all user data — back it up regularly and restrict
  access.
- Do not expose the WebUI directly to the public internet without a reverse
  proxy that adds authentication, rate limiting, and TLS.

## Reporting issues

Please report security issues privately to the maintainer instead of opening a
public issue containing credentials, tokens, private prompts, or private images.
