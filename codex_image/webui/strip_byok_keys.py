from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path
from typing import Any


def _strip_params(obj: Any) -> bool:
    if isinstance(obj, dict) and isinstance(obj.get("params"), dict):
        params = obj["params"]
        if "byok_api_key" in params:
            obj["params"] = {k: v for k, v in params.items() if k != "byok_api_key"}
            return True
    return False


def _strip_metadata_files(source_data_root: Path, *, dry_run: bool) -> int:
    cleaned = 0
    for suffix in ("metadata.json", "request.json"):
        for path in source_data_root.rglob(f"*.{suffix}"):
            try:
                raw = path.read_text(encoding="utf-8")
                data = json.loads(raw)
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(data, dict):
                continue
            changed = _strip_params(data)
            for key in ("params",):
                pass
            if changed:
                cleaned += 1
                if not dry_run:
                    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    legacy_flat = list(source_data_root.glob("*.metadata.json")) + list(source_data_root.glob("*.request.json"))
    for path in legacy_flat:
        try:
            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict) and _strip_params(data):
            cleaned += 1
            if not dry_run:
                path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return cleaned


def _strip_index_db(index_db: Path, *, dry_run: bool) -> int:
    if not index_db.exists():
        return 0
    cleaned = 0
    with closing(sqlite3.connect(index_db)) as connection:
        rows = connection.execute("select task_id, summary_json from task_index").fetchall()
        for task_id, raw in rows:
            try:
                summary = json.loads(str(raw))
            except json.JSONDecodeError:
                continue
            if isinstance(summary, dict) and _strip_params(summary):
                cleaned += 1
                if not dry_run:
                    connection.execute(
                        "update task_index set summary_json = ? where task_id = ?",
                        (json.dumps(summary, ensure_ascii=False), task_id),
                    )
        if not dry_run:
            connection.commit()
    return cleaned


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Strip persisted byok_api_key from task metadata and the task index DB.")
    parser.add_argument("--source-data-root", type=Path, required=True, help="Path to the webui source-data directory")
    parser.add_argument("--dry-run", action="store_true", help="Report what would change without writing")
    args = parser.parse_args(argv)

    root: Path = args.source_data_root
    if not root.exists():
        print(f"source-data root not found: {root}", file=sys.stderr)
        return 2

    index_db = root / "webui-task-index.db"
    files_cleaned = _strip_metadata_files(root, dry_run=args.dry_run)
    db_cleaned = _strip_index_db(index_db, dry_run=args.dry_run)

    verb = "would strip" if args.dry_run else "stripped"
    print(f"{verb} byok_api_key from {files_cleaned} metadata/request file(s) and {db_cleaned} index row(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
