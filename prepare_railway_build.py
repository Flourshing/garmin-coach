"""Stage only explicitly approved program files for a Railway source upload."""
import hashlib
import json
import shutil
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FILES = (
    "Dockerfile", ".dockerignore", "railway.json", "requirements.txt",
    "collect.py", "garmin_service.py", "garmin_mcp_server.py", "garmin_data.py", "garmin_extended.py",
    "prepare_openclaw.py", "prepare_daily_job.py",
    "coach/AGENTS.md", "coach/MEMORY.md", "coach/SOUL.md", "coach/USER.md", "coach/PREFERENCES.md",
    "deploy/runtime-package.json", "deploy/cloud_start.py",
    "deploy/codex-restricted-settings.json", "deploy/deepseek-provider.json",
    "deploy/daily-report-prompt.txt",
)


def stage():
    # Fresh directories avoid stale files from an earlier upload.
    target = ROOT / ".private" / ("railway-build-" + uuid.uuid4().hex[:12])
    target.mkdir(parents=True)
    manifest = []
    for relative in FILES:
        source = ROOT / relative
        if source.is_symlink() or not source.is_file():
            raise ValueError(f"Expected an ordinary source file: {relative}")
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        data = destination.read_bytes()
        manifest.append({"path": relative, "bytes": len(data),
                         "sha256": hashlib.sha256(data).hexdigest()})
    actual = {p.relative_to(target).as_posix() for p in target.rglob("*") if p.is_file()}
    if actual != set(FILES):
        raise ValueError("Unexpected build-context files")
    status = {"path": str(target), "source_files": manifest,
              "total_bytes": sum(p["bytes"] for p in manifest),
              "private_data_included": False, "uploaded": False}
    (ROOT / ".private" / "railway-build-status.json").write_text(
        json.dumps(status, indent=2), encoding="utf-8")
    print(json.dumps({"staged_files": len(manifest),
                      "total_bytes": status["total_bytes"],
                      "private_data_included": False, "uploaded": False}))


if __name__ == "__main__":
    stage()
