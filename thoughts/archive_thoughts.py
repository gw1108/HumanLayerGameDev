import os

from send2trash import send2trash

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shared")


def archive_thoughts(base: str = BASE, run_id: str | None = None) -> list[str]:
    """Send .md files under base/*/ to the OS trash (Recycle Bin on Windows).

    When run_id is provided, only files whose name contains that tag (e.g.
    "tag-a3b7c2") are trashed. This keeps concurrent pipeline runs isolated:
    each run only cleans up its own output files and leaves other runs'
    in-flight files untouched. When run_id is None, all .md files are trashed.
    """
    trashed = []
    for folder in os.listdir(base):
        folder_path = os.path.join(base, folder)
        if not os.path.isdir(folder_path):
            continue
        for f in os.listdir(folder_path):
            if not f.endswith(".md"):
                continue
            if run_id is not None and run_id not in f:
                continue
            src = os.path.join(folder_path, f)
            send2trash(src)
            trashed.append(f"  {folder}/{f}")
    return trashed


if __name__ == "__main__":
    import sys

    run_id = sys.argv[1] if len(sys.argv) > 1 else None
    trashed = archive_thoughts(run_id=run_id)
    if trashed:
        print(f"Sent {len(trashed)} file(s) to the Recycle Bin:")
        print("\n".join(trashed))
    else:
        print("Nothing to send to the Recycle Bin.")

    input("\nPress Enter to close...")
