# Contributing

Thanks for your interest in improving Fei Yang Lab.

## Before opening a pull request

1. Keep changes focused.
2. Do not commit local inputs, outputs, credentials, task databases, or logs.
3. Run the relevant checks:

```bash
# Python tests (note: PYTHONPATH=. is required)
PYTHONPATH=. .venv/bin/python -m pytest tests/ -v

# Frontend build checks
npm run check:webui
```

4. Frontend TypeScript and CSS changes should include the generated static assets
   under `codex_image/webui/static/`.

5. Changes to `explore.js`, `explore.css`, or `explore.html` do not require a
   build step (they are served as-is).

## Key modules (this fork)

If your change touches multi-user isolation or sharing, be aware of:

- `codex_image/webui/owner.py` — identity cookies, `OwnerStore`, `resolve_owner`.
- `codex_image/webui/share_store.py` — `shared_tasks` table, CRUD, pagination.
- `codex_image/webui/events.py` — SSE event enrichment with `shared_at`.
- `codex_image/webui/routes/generation.py` — BYOK model override logic.
- `codex_image/webui/routes/assets.py` — ownership-checked image routes.
- `codex_image/webui/task_enrichment.py` — URL rewriting and file URL enrichment.

## Testing notes

- Python tests require `PYTHONPATH=.` because test imports use
  `codex_image.webui.*` absolute paths.
- `python-multipart` is required for form-data tests (included in
  `requirements-webui.txt`).
- The share integration test suite (`tests/test_webui_share*.py`) covers share
  CRUD, public listing, and asset access control.
