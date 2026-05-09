#!/usr/bin/env python3
"""Compute a thoughts/shared/ markdown file path. Does NOT write the file.

Returns a unique, dated, conflict-free path on stdout. The caller (Claude)
writes the file directly via the Write tool. This avoids shell-quoting bugs
that occurred when large markdown blobs were passed as a CLI argument.

Usage:
  python create_thought.py <main_folder> <file_name_description> [ticket]

Example:
  python create_thought.py plans "lazy-sundae-mechanic" tag-a3b7c2
  -> /abs/path/to/thoughts/shared/plans/2026-04-30-ENG-tag-a3b7c2-lazy-sundae-mechanic.md
"""
import sys
import os
from datetime import datetime, timezone


def main():
    if len(sys.argv) < 3:
        print(
            "Usage: create_thought.py <main_folder> <file_name_description> [ticket]",
            file=sys.stderr,
        )
        sys.exit(1)

    main_folder = sys.argv[1]
    description = sys.argv[2]
    ticket = sys.argv[3] if len(sys.argv) > 3 else None

    project_root = os.path.dirname(os.path.abspath(__file__))
    folder_path = os.path.join(project_root, "thoughts", "shared", main_folder)
    os.makedirs(folder_path, exist_ok=True)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    base_name = f"{today}-ENG-{ticket}-{description}" if ticket else f"{today}-ENG-{description}"

    file_path = os.path.join(folder_path, f"{base_name}.md")

    if os.path.exists(file_path):
        version = 2
        while True:
            candidate = os.path.join(folder_path, f"{base_name}-v{version}.md")
            if not os.path.exists(candidate):
                file_path = candidate
                break
            version += 1

    print(file_path)


if __name__ == "__main__":
    main()
