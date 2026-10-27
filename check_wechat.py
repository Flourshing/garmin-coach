"""Read selected WeChat integration status without exposing identifiers or tokens."""
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATE = ROOT / ".private/openclaw"
index = STATE / "openclaw-weixin/accounts.json"
accounts = json.loads(index.read_text(encoding="utf-8")) if index.exists() else []
safe = {"bound_account_count": len(accounts)}
owner = None
selected_account = None
for account in accounts:
    account_file = STATE / "openclaw-weixin/accounts" / (account + ".json")
    if account_file.exists():
        record = json.loads(account_file.read_text(encoding="utf-8"))
        safe["bound_owner_present"] = bool(record.get("userId"))
        safe["bound_token_present"] = bool(record.get("token"))
        if len(accounts) == 1:
            owner = record.get("userId")
            selected_account = account
dbpath = STATE / "agents/main/agent/openclaw-agent.sqlite"
db = sqlite3.connect(dbpath.resolve().as_uri() + "?mode=ro", uri=True, timeout=5)
tables = [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
safe["session_table_candidates"] = [table for table in tables if "session" in table and "transcript" not in table and "fts" not in table]
if "sessions" in tables:
    safe["session_columns"] = [row[1] for row in db.execute("PRAGMA table_info(sessions)")]
safe["hello_session_count"] = db.execute("SELECT count(DISTINCT session_id) FROM session_transcript_fts WHERE role='user' AND text LIKE ?", ("%你好%",)).fetchone()[0]
hello_sessions = [row[0] for row in db.execute("SELECT DISTINCT session_id FROM session_transcript_fts WHERE role='user' AND text LIKE ?", ("%你好%",))]
if len(hello_sessions) == 1:
    replies = [row[0] for row in db.execute("SELECT text FROM session_transcript_fts WHERE session_id=? AND role='assistant' ORDER BY rowid", (hello_sessions[0],))]
    safe["assistant_reply_count"] = len(replies)
    if replies:
        safe["last_assistant_reply"] = replies[-1]
db.close()
quote_path = STATE / "openclaw-weixin/ref-messages.sqlite"
if selected_account and owner and quote_path.exists():
    quotes = sqlite3.connect(quote_path.resolve().as_uri() + "?mode=ro", uri=True, timeout=5)
    safe["bound_owner_message_counts"] = dict(quotes.execute(
        "SELECT direction,count(*) FROM quote_messages WHERE account_id=? AND conversation_id=? GROUP BY direction",
        (selected_account, owner),
    ))
    safe["daily_report_outbound_count"] = quotes.execute(
        "SELECT count(*) FROM quote_messages WHERE account_id=? AND conversation_id=? AND direction='outbound' AND body LIKE ?",
        (selected_account, owner, "%佳明日报%"),
    ).fetchone()[0]
    quotes.close()
job_status = STATE.parent / "daily-job-status.json"
if job_status.exists():
    job_id = json.loads(job_status.read_text(encoding="utf-8")).get("id")
    shared = sqlite3.connect((STATE / "state/openclaw.sqlite").resolve().as_uri() + "?mode=ro", uri=True, timeout=5)
    row = shared.execute("SELECT enabled,state_json FROM cron_jobs WHERE job_id=?", (job_id,)).fetchone()
    if row:
        job_state = json.loads(row[1])
        safe["daily_job_enabled"] = bool(row[0])
        safe["daily_job_result"] = {key: job_state.get(key) for key in ("lastStatus", "lastRunStatus", "lastDeliveryStatus", "lastDelivered", "lastRunAtMs") if key in job_state}
    safe["daily_job_receipts"] = [list(row) for row in shared.execute(
        "SELECT status,delivery_attempt_state FROM cron_run_receipts WHERE job_id=? ORDER BY started_at_ms DESC LIMIT 3", (job_id,)
    )]
    shared.close()
safe["report_file_present"] = (STATE.parent / "coach-workspace/reports/2026-10-23.md").exists()
(ROOT / ".private/wechat-check-status.json").write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(safe, ensure_ascii=False))
