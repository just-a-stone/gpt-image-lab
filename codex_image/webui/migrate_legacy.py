from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path
from typing import Any

from codex_image.webui.owner import OwnerStore, compute_key_hash


def _update_index_db(index_db: Path, owner_id: str, *, dry_run: bool) -> int:
    if not index_db.exists():
        return 0
    updated = 0
    with closing(sqlite3.connect(index_db)) as connection:
        rows = connection.execute(
            "select task_id, summary_json from task_index where owner = '' or owner is null"
        ).fetchall()
        for task_id, raw in rows:
            try:
                summary = json.loads(str(raw))
            except json.JSONDecodeError:
                continue
            if isinstance(summary, dict):
                summary["owner"] = owner_id
            if not dry_run:
                connection.execute(
                    "update task_index set owner = ?, summary_json = ? where task_id = ?",
                    (owner_id, json.dumps(summary, ensure_ascii=False), task_id),
                )
            updated += 1
        if not dry_run:
            connection.commit()
    return updated


def _update_metadata_files(source_data_root: Path, owner_id: str, *, dry_run: bool) -> int:
    updated = 0
    for pattern in ("**/*.metadata.json", "*.metadata.json"):
        for path in source_data_root.glob(pattern):
            try:
                raw = path.read_text(encoding="utf-8")
                data = json.loads(raw)
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(data, dict):
                continue
            if str(data.get("owner") or ""):
                continue
            data["owner"] = owner_id
            updated += 1
            if not dry_run:
                path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return updated


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Bind legacy ownerless tasks to a specific owner (derived from an API key)."
    )
    parser.add_argument("--source-data-root", type=Path, required=True, help="Path to the webui source-data directory")
    parser.add_argument("--owner-key", type=str, required=True, help="API key whose owner_id will claim legacy tasks")
    parser.add_argument("--dry-run", action="store_true", help="Report what would change without writing")
    args = parser.parse_args(argv)

    root: Path = args.source_data_root
    if not root.exists():
        print(f"source-data root not found: {root}", file=sys.stderr)
        return 2

    index_db = root / "webui-task-index.db"
    store = OwnerStore(index_db)
    key_hash = compute_key_hash(args.owner_key)
    owner_id = store.get_or_create(key_hash)

    db_count = _update_index_db(index_db, owner_id, dry_run=args.dry_run)
    file_count = _update_metadata_files(root, owner_id, dry_run=args.dry_run)

    verb = "would bind" if args.dry_run else "bound"
    print(f"{verb} {db_count} legacy task(s) in the index and {file_count} metadata file(s) to owner {owner_id[:10]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
