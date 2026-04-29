#!/usr/bin/env python3
import sys
import os
from datetime import datetime, timezone
import time

# Creates a timestamped markdown file under /thoughts/shared/. Call this when you need to persist any written output. Returns the full path of the created file.
# In any skill that needs to save things out, simply tell that claude skill/command to do the following:
# Persist the research/plan/implement by running: python create_thought.py <folder> <file_name_description> <content> [ticket].
# Print the returned path of the file created.
def main():
    if len(sys.argv) < 4:
        print(
            "Usage: create_thought.py <main_folder> <file_name_description> <file_contents> [ticket]",
            file=sys.stderr,
        )
        sys.exit(1)

    main_folder = sys.argv[1]
    description = sys.argv[2]
    contents = sys.argv[3]
    ticket = sys.argv[4] if len(sys.argv) > 4 else None

    project_root = os.path.dirname(os.path.abspath(__file__))
    folder_path = os.path.join(project_root, "thoughts", "shared", main_folder)
    os.makedirs(folder_path, exist_ok=True)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    base_name = f"{today}-ENG-{ticket}-{description}" if ticket else f"{today}-ENG-{description}"

    file_path = os.path.join(folder_path, f"{base_name}.md")

    if os.path.exists(file_path):
        deadline = time.time() + 60
        version = 2
        while True:
            if time.time() > deadline:
                print("Timeout: could not find a non-conflicting filename.", file=sys.stderr)
                sys.exit(1)
            candidate = os.path.join(folder_path, f"{base_name}-v{version}.md")
            if not os.path.exists(candidate):
                file_path = candidate
                break
            version += 1

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(contents)

    print(file_path)


if __name__ == "__main__":
    main()
