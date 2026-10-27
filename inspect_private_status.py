"""Read only aggregate local database status; never select credential values."""
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
result = {}
for name, path in (
    ("shared", ROOT / ".private/openclaw/state/openclaw.sqlite"),
    ("agent", ROOT / ".private/openclaw/agents/main/agent/openclaw-agent.sqlite"),
):
    if not path.exists():
        result[name] = {"exists": False}
        continue
    db = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=3)
    tables = [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    safe = {"tables": [t for t in tables if any(x in t for x in ("auth", "config_machine", "cron", "transcript", "message"))]}
    for table in safe["tables"]:
        # Table identifiers come solely from the local schema, never user input.
        safe[table] = {"rows": db.execute('SELECT count(*) FROM "' + table.replace('"', '""') + '"').fetchone()[0]}
        safe[table]["columns"] = [row[1] for row in db.execute('PRAGMA table_info("' + table.replace('"', '""') + '")')]
    if "config_machine_state" in tables:
        safe["machine_keys"] = [row[0] for row in db.execute("SELECT state_key FROM config_machine_state")]
        safe["saved_profile_count"] = db.execute("SELECT count(*) FROM config_machine_state, json_each(value_json, '$.profiles') WHERE state_key='authProfiles.store'").fetchone()[0]
        safe["garmin_profile_metadata"] = [list(row) for row in db.execute(
            "SELECT json_extract(value_json,'$.profiles.\"openai:garmin-plus\".type'), "
            "json_extract(value_json,'$.profiles.\"openai:garmin-plus\".provider'), "
            "json_extract(value_json,'$.profiles.\"openai:garmin-plus\".expires') "
            "FROM config_machine_state WHERE state_key='authProfiles.store'"
        )]
    if "transcript_events" in tables:
        safe["test_event_types"] = [list(row) for row in db.execute("SELECT json_extract(event_json,'$.type'),json_extract(event_json,'$.message.role'),json_extract(event_json,'$.message.stopReason') FROM transcript_events WHERE session_id=?", ("garmin-model-connection-test",))]
    result[name] = safe
    db.close()
print(json.dumps(result))
