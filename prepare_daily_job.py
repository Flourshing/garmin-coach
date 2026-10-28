"""Prepare one disabled 08:00 job for the verified owner; optionally test once."""
import argparse
import json
import os
import re
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATE = Path(os.environ.get("OPENCLAW_STATE_DIR", ROOT / ".private/openclaw"))
STATUS = STATE.parent / "daily-job-status.json"
NAME = "garmin-daily-0800"


def cli(*args, timeout=90):
    command = (["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "openclaw.ps1")]
               if os.name == "nt" else ["openclaw"])
    result = subprocess.run(command + list(args), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    decoder = json.JSONDecoder()
    for pos, char in enumerate(result.stdout):
        if char != "{":
            continue
        try:
            data, _ = decoder.raw_decode(result.stdout[pos:])
        except ValueError:
            continue
        if isinstance(data, dict) and any(key in data for key in ("jobs", "id", "ok", "job", "runId", "status")):
            if result.returncode:
                raise RuntimeError("OpenClaw command failed; inspect private job status before retrying.")
            return data
    raise RuntimeError("OpenClaw returned no recognized result; inspect state before retrying.")


def save(value):
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    temp = STATUS.with_suffix(".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(STATUS)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-test", action="store_true")
    opts = parser.parse_args()
    accounts = json.loads((STATE / "openclaw-weixin/accounts.json").read_text(encoding="utf-8"))
    if len(accounts) != 1:
        raise RuntimeError("Expected exactly one bound WeChat account.")
    account = accounts[0]
    if not re.fullmatch(r"[A-Za-z0-9_-]+", account):
        raise RuntimeError("Unexpected account identifier.")
    record = json.loads((STATE / "openclaw-weixin/accounts" / (account + ".json")).read_text(encoding="utf-8"))
    owner = record.get("userId")
    if not owner:
        raise RuntimeError("The bound owner is missing.")
    quotes = sqlite3.connect((STATE / "openclaw-weixin/ref-messages.sqlite").resolve().as_uri() + "?mode=ro", uri=True)
    inbound = quotes.execute("SELECT count(*) FROM quote_messages WHERE account_id=? AND conversation_id=? AND direction='inbound'", (account, owner)).fetchone()[0]
    quotes.close()
    if not inbound:
        raise RuntimeError("No verified inbound message from the bound owner.")
    jobs = cli("automations", "list", "--all", "--json").get("jobs", [])
    matches = [job for job in jobs if job.get("name") == NAME]
    if len(matches) > 1:
        raise RuntimeError("Duplicate daily jobs require review.")
    if matches:
        job = matches[0]
        delivery = job.get("delivery", {})
        if delivery.get("to") != owner or delivery.get("accountId") != account:
            raise RuntimeError("Existing job recipient does not match the verified owner.")
    else:
        prompt = (ROOT / "deploy/daily-report-prompt.txt").read_text(encoding="utf-8").strip()
        result = cli("automations", "add", "--name", NAME,
                     "--description", "Garmin China daily report, pending hosted deployment",
                     "--declaration-key", "garmin-cn-daily-0800", "--agent", "main",
                     "--cron", "0 8 * * *", "--tz", "Asia/Shanghai", "--exact", "--disabled",
                     "--session", "isolated", "--message", prompt,
                     "--timeout-seconds", "180", "--tools", "bundle-mcp,read,write,tool_search,tool_describe,tool_call",
                     "--announce", "--channel", "openclaw-weixin", "--account", account, "--to", owner, "--json")
        job = result.get("job", result)
    if job.get("enabled"):
        raise RuntimeError("Daily job was unexpectedly enabled; inspect before proceeding.")
    previous = json.loads(STATUS.read_text(encoding="utf-8")) if STATUS.exists() else {}
    safe = {"id": job["id"], "name": NAME, "enabled": False, "schedule": job.get("schedule"),
            "verified_owner_only": True, "cloud_deployed": False}
    safe.update({key: previous[key] for key in ("test_requested_at", "test_result") if key in previous})
    save(safe)
    if opts.run_test:
        if safe.get("test_requested_at"):
            raise RuntimeError("A test was already requested. Inspect its receipt rather than resend.")
        safe["test_requested_at"] = datetime.now(timezone.utc).isoformat()
        save(safe)
        result = cli("automations", "run", job["id"], "--wait", "--wait-timeout", "4m", "--json", timeout=300)
        safe["test_result"] = {key: result.get(key) for key in ("ok", "ran", "status", "queued", "runId") if key in result}
        save(safe)
    print(json.dumps(safe, ensure_ascii=False))


if __name__ == "__main__":
    main()
