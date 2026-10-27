"""Read only this project's explicit validation conversation, without another model call."""
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SESSION = "garmin-coach-validation-20261023"
path = ROOT / ".private/openclaw/agents/main/agent/openclaw-agent.sqlite"
db = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=5)
tools = [row[0] for row in db.execute(
    "SELECT json_extract(CASE WHEN j.type='object' THEN j.value ELSE '{}' END,'$.name') "
    "FROM transcript_events e, json_each(CASE WHEN json_valid(e.event_json) THEN e.event_json ELSE '{}' END,'$.message.content') j "
    "WHERE e.session_id=? AND json_extract(CASE WHEN j.type='object' THEN j.value ELSE '{}' END,'$.type') IN ('toolCall','tool_use')", (SESSION,)
)]
texts = [row[0] for row in db.execute(
    "SELECT text FROM session_transcript_fts WHERE session_id=? AND role='assistant'", (SESSION,)
)]
health_dispatch = db.execute(
    "SELECT count(*) FROM transcript_events e, "
    "json_each(CASE WHEN json_valid(e.event_json) THEN e.event_json ELSE '{}' END,'$.message.content') j "
    "WHERE e.session_id=? AND json_extract(CASE WHEN j.type='object' THEN j.value ELSE '{}' END,'$.name')='tool_call' "
    "AND instr(j.value,'get_health_summary')>0", (SESSION,)
).fetchone()[0] > 0
db.close()
report = "\n\n".join(text for text in texts if text.strip())
safe = {"report_present": bool(report), "tools": tools, "health_tool_called": health_dispatch or any("health_summary" in (tool or "") for tool in tools)}
if report:
    (ROOT / ".private/coach-first-report.md").write_text(report, encoding="utf-8")
    safe["report"] = report
(ROOT / ".private/coach-transcript-status.json").write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(safe, ensure_ascii=False))
