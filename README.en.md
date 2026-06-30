<h1 align="center">Fei Yang Lab</h1>

<p align="center">
  <sub>GPT-image-2 WebUI workbench · BYOK self-service keys · Multi-user isolation · Public share gallery · Docker deployment</sub>
</p>

<p align="center">
  <a href="https://github.com/just-a-stone/gpt-image-lab/releases"><img alt="release" src="https://img.shields.io/github/v/release/just-a-stone/gpt-image-lab?style=flat-square&logo=github&label=release&color=0EA5E9"></a>
  <a href="https://github.com/just-a-stone/gpt-image-lab/actions/workflows/ci.yml"><img alt="CI status" src="https://github.com/just-a-stone/gpt-image-lab/actions/workflows/ci.yml/badge.svg?branch=main&event=push"></a>
  <a href="https://github.com/just-a-stone/gpt-image-lab/commits/main"><img alt="last commit" src="https://img.shields.io/github/last-commit/just-a-stone/gpt-image-lab?style=flat-square&logo=github&label=last%20commit&color=10B981"></a>
  <a href="https://github.com/just-a-stone/gpt-image-lab/stargazers"><img alt="stars" src="https://img.shields.io/github/stars/just-a-stone/gpt-image-lab?style=flat-square&logo=github&label=stars&color=0284C7"></a>
</p>

<p align="center">
  <img alt="license AGPL-3.0-only" src="https://img.shields.io/badge/license-AGPL--3.0--only-22C55E?style=flat-square">
  <img alt="Python 3.11+" src="https://img.shields.io/badge/python-3.11%2B-3776AB?style=flat-square&logo=python&logoColor=white">
  <img alt="FastAPI WebUI" src="https://img.shields.io/badge/WebUI-FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white">
  <img alt="Docker" src="https://img.shields.io/badge/Docker-ready-2496ED?style=flat-square&logo=docker&logoColor=white">
  <img alt="BYOK" src="https://img.shields.io/badge/BYOK-supported-8B5CF6?style=flat-square">
  <img alt="Multi-user" src="https://img.shields.io/badge/multi--user-isolated-F59E0B?style=flat-square">
</p>

<p align="center">
  English · <a href="README.md">中文</a>
</p>

---

## Overview

Fei Yang Lab is an enhanced fork of [iLab GPT Conjure](https://github.com/kadevin/ilab-gpt-conjure), an AI image generation WebUI workbench for GPT-image-2 with a companion CLI for local automation.

Key additions in this fork:

- **BYOK (Bring Your Own Key)**: Users configure their own OpenAI-compatible API key, base URL, and image model directly in the browser — no server-side preset needed.
- **Multi-user data isolation**: Tasks, reference assets, and gallery items are isolated per user. Identity is based on a random cookie that survives restarts.
- **Public share gallery** (`/explore`): Users can share tasks to a public browsing page with multi-image gallery, prompt copy, and infinite scroll.
- **Docker deployment**: Built-in Dockerfile and docker-compose.yml for multi-user shared deployments.
- **SSE heartbeat**: Keeps SSE connections alive through Docker / reverse-proxy environments.
- **Environment variable controls**: `WEBUI_OWNER_SECRET`, `WEBUI_DISABLE_DELETION`, `CODEX_IMAGE_REQUEST_TIMEOUT_SECONDS`, and more.

## Features

### Inherited from upstream (fully preserved)

- GPT-image-2 text-to-image, reference-image generation, and image editing workflows.
- Codex Image, Codex Responses, and OpenAI-compatible API access.
- Concurrent task execution, local queue state, paged history library, thumbnails, and result archive.
- Independent `/history` page with SQLite-backed pagination, search, filters, grid/list views, and lazy detail loading.
- Shared gallery references, recent reference images, color chips, prompt snippet chips, and reusable prompt templates.
- Layered input-image editor with multi-image composition, ratio-locked transform, Shift free transform, and local erasing.
- System Settings with 13 languages, first-launch browser detection, and browser-local preference.
- CLI support for generation, image references, image edits, masks, and dry runs.

### New in this fork

- **BYOK self-service keys**: Frontend popover for API Key / Base URL / Image Model input, stored in browser `localStorage`, sent with form data, never persisted server-side.
- **Multi-user isolation**: Each user gets a random `owner_id` (HMAC-signed Cookie, 30-day TTL); task index, gallery, and reference assets are owner-scoped; SSE events, image routes, and API endpoints enforce ownership checks.
- **Public share gallery** (`/explore`):
  - Task card "Share" button → confirmation dialog (editable share note) → generates `share_id`.
  - Share button auto-hides for already-shared tasks.
  - `/explore` page supports infinite scroll, multi-image gallery modal (prev/next, thumbnail strip, keyboard arrows), and one-click prompt copy.
  - Uses independent `shared_tasks` table; `public_author_id` is HMAC-anonymized; response is an allowlist of public fields only.
- **Docker deployment**: `Dockerfile` + `docker-compose.yml` with data volume mapping to `./data` and built-in health check.
- **SSE heartbeat**: Sends a keep-alive comment every 15 seconds to survive Docker / Nginx proxy timeouts.
- **BYOK image model fix**: The BYOK image model setting now actually takes effect (previously overridden by the default `gpt-image-2`).
- **CLI migration tools**: `migrate_legacy.py` (bind ownerless tasks to a specific user), `strip_byok_keys.py` (purge historically persisted BYOK keys).

## Authentication modes

### BYOK self-service key (new in this fork)

Click the "Bring Your Own Key" button in the top-right corner, enter your OpenAI-compatible API Key, Base URL (e.g. `https://api.openai.com/v1`), and image model name (e.g. `dall-e-3`, `gpt-image-2`). Credentials are stored only in the browser's `localStorage`, sent with the form submission, held in memory during task execution, and never written to the database or logs.

### OpenAI-compatible API (upstream)

Configure API provider cards in System Settings (base URL, API key, model name, API mode, concurrency). Recommended for stable integrations and team use.

### Advanced local mode: Codex / ChatGPT OAuth

Optionally reuse a local Codex / ChatGPT OAuth session to call internal ChatGPT backend endpoints. Local personal workflows only; endpoints may change without notice.

## Requirements

- Python 3.11 or newer.
- WebUI dependencies from `requirements-webui.txt`.
- Optional frontend tooling from `package.json` when editing TypeScript or CSS (esbuild + Konva).
- Docker 20.10+ and Docker Compose V2 for containerized deployment.

## Quick start

### Option 1: Docker (recommended for multi-user)

```bash
git clone https://github.com/just-a-stone/gpt-image-lab.git
cd gpt-image-lab

# Generate identity secret (must be fixed for multi-user, otherwise all users
# lose their sessions on restart)
echo "WEBUI_OWNER_SECRET=$(openssl rand -hex 32)" > .env

# Edit docker-compose.yml environment variables as needed
docker compose up -d
```

Then open `http://localhost:8787/`.

Data (inputs/outputs/gallery/settings/task database) is persisted in `./data/`.

### Option 2: Local source run

```bash
git clone https://github.com/just-a-stone/gpt-image-lab.git
cd gpt-image-lab
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-webui.txt

.venv/bin/python -m uvicorn codex_image.webui.app:app --host 127.0.0.1 --port 8787 --no-access-log
```

Then open `http://127.0.0.1:8787/`.

### Option 3: One-click launchers

macOS: double-click `Start WebUI.command`
Windows: double-click `Start WebUI.bat`

## Environment variables

| Variable | Description | Default |
| --- | --- | --- |
| `WEBUI_OWNER_SECRET` | HMAC signing secret for user identity cookies. **Must be fixed** in multi-user deployments, otherwise all users lose sessions on restart. Generate with `openssl rand -hex 32`. | Random (lost on restart, prints warning) |
| `WEBUI_DISABLE_DELETION` | Set to `1`/`true`/`yes`/`on` to disable delete/archive functionality. Recommended for shared multi-user deployments. | Empty (deletion allowed) |
| `CODEX_IMAGE_REQUEST_TIMEOUT_SECONDS` | Per-request timeout for image generation in seconds. | 300 |
| `CODEX_IMAGE_DEBUG_SSE` | SSE debug logging. Leave empty in production. | Empty |

## Multi-user isolation

This fork implements full user-level data isolation:

- **Identity**: A random `owner_id` (e.g. `u_a1b2c3d4e5f6...`) is generated on first visit, persisted via an HMAC-signed Cookie (30-day TTL).
- **Recovery**: If the cookie is lost, a `key_hash` (browser-fingerprint-based recovery anchor) can re-associate existing data.
- **Isolation scope**:
  - Task index (`task_index` table `owner` column)
  - Gallery items (`gallery_items` filtered by owner)
  - Reference assets (`reference_assets` filtered by owner)
  - SSE event stream (only current owner's task events are pushed)
  - Image routes (`/api/outputs/`, `/api/inputs/` validate file ownership)
- **Shared resources**: Gallery categories, prompt snippets, and prompt templates remain globally shared (templates are designed as reusable structures).

### CLI migration tools

```bash
# Bind ownerless tasks (empty owner) to a specific user
.venv/bin/python -m codex_image.webui.migrate_legacy --owner u_xxxx --db output/webui-outputs/source-data/webui-task-index.db

# Purge BYOK API keys persisted in historical task params (older versions may have stored them)
.venv/bin/python -m codex_image.webui.strip_byok_keys --db output/webui-outputs/source-data/webui-task-index.db
```

## Public share gallery

Visit `/explore` to browse all publicly shared tasks.

- **Share**: Click the "Share" button on a task card → confirmation dialog → task appears in the public gallery.
- **Unshare**: Click "Unshare" on an already-shared task.
- **Browse**: The `/explore` page supports infinite scroll, multi-image gallery modal (arrow keys to navigate), and one-click prompt copy.
- **Security**: Sharing uses an independent `share_id` (not the raw task_id); responses contain only allowlisted public fields; `public_author_id` is HMAC-anonymized; shared images have a 5-minute cache (unsharing takes effect within 5 minutes).

## WebUI usage

1. **Authentication**: Select an auth source at the top (BYOK / Codex / API), or click "Bring Your Own Key" to configure BYOK.
2. **API settings**: Open System Settings to manage API provider cards, Codex channel, interface language, storage paths, and notification preferences.
3. **Reference images**: Upload, drag-and-drop, paste, use recent uploads, or pick from the public gallery.
4. **Prompt**: Type directly or insert `@` gallery chips, `#` color chips, `~` snippet chips.
5. **Parameters**: Set count, size, orientation, quality, output format, and compression.
6. **Generate**: Start generation, track progress in the left task list, review/select/retry/download/archive results in the preview area.
7. **History**: Full history is searchable and filterable at `/history`.
8. **Share**: Click the "Share" button on a task card to publish to the `/explore` public gallery.

## Prompt chips

The prompt editor supports three atomic chip types:

- `@` gallery chip: searches the public gallery and inserts the selected image into reference inputs.
- `#` color chip: inserts a hexadecimal color value (e.g. `#FF6600`).
- `~` snippet chip: inserts a saved prompt snippet by short tag; the editor shows the tag, the model receives the full expanded text.

## CLI

```bash
.venv/bin/python -m codex_image generate --prompt "A clean product photo of a ceramic mug" --out output/mug.png
```

Use `--help` for all CLI options.

## Development

```bash
# Run tests
PYTHONPATH=. .venv/bin/python -m pytest tests/ -v

# Frontend checks
npm run check:webui
```

When changing frontend TypeScript or CSS, run `npm install` first, then commit the generated browser assets in `codex_image/webui/static/`.

Editing `explore.js` / `explore.css` / `explore.html` requires no build step (static-served).

### Project structure (new files in this fork)

```
codex_image/webui/
├── owner.py              # User identity core: HMAC Cookie, OwnerStore
├── share_store.py        # shared_tasks table CRUD + cursor pagination
├── feature_flags.py      # Environment variable feature flags
├── migrate_legacy.py     # CLI: migrate ownerless tasks
├── strip_byok_keys.py    # CLI: purge persisted BYOK keys
├── routes/
│   ├── share.py          # Share CRUD + public gallery API
│   ├── assets.py         # Ownership-checked image routes
│   └── session.py        # Session/identity routes
├── frontend/src/
│   ├── byok.ts           # BYOK frontend UI
│   └── share-dialog.ts   # Share confirmation dialog
└── static/
    ├── explore.html      # Public gallery page
    ├── explore.css       # Gallery styles
    └── explore.js        # Gallery interaction (infinite scroll, multi-image modal)
```

## Relationship to upstream

This project is forked from [kadevin/ilab-gpt-conjure](https://github.com/kadevin/ilab-gpt-conjure) and continues development under the same AGPL-3.0 license. Upstream's portable packages, release packaging workflows, and WeChat contact information do not apply to this fork.

## License

This project is licensed under GNU AGPLv3. See `LICENSE`.

If you modify this software and make it available to users over a network, you must also make the corresponding source code available under the same license.
