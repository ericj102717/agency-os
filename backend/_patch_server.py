import sys

with open('/home/user/workspace/command-center/server.py', 'r') as f:
    code = f.read()

# 1. Add feedback_engine import
old = "from health_monitor import monitor as _health_monitor"
new = "from health_monitor import monitor as _health_monitor\nfrom feedback_engine import feedback_engine as _feedback_engine\nfrom feedback_engine import FeedbackEngine"
if old in code:
    code = code.replace(old, new, 1)
    print("1. Added feedback_engine import")
else:
    print("ERROR: health_monitor import not found")

# 2. Add helper function and feedback endpoints
marker = "# ---- ADMIN ENDPTS ----"
if marker not in code:
    marker = "# ---- ADMIN ENDPOINTS ----"

feedback_block = '''# ---- FEEDBACK ENDPOINTS ----

def _get_business_context():
    """Derive business_id and demo state from server state."""
    try:
        conn = sqlite3.connect(DB_PATH, timeout=3)
        row = conn.execute("SELECT business_id, is_demo_mode FROM demo_state WHERE id=1").fetchone()
        conn.close()
        if row:
            return row[0] or "default", bool(row[1])
        return "default", True
    except Exception:
        return "default", True

@app.post("/api/v2/feedback/recommendation")
def v2_submit_recommendation_feedback(payload: dict = None, x_api_key: str = None):
    check_auth(x_api_key)
    if not payload:
        return {"status": "error", "error": "No payload provided"}
    business_id, is_demo = _get_business_context()
    environment = "demo" if is_demo else "live"
    rec_id = payload.get("recommendation_id", "")
    rec_key = payload.get("recommendation_key", rec_id)
    rec_type = payload.get("recommendation_type", "")
    source = payload.get("source", "")
    date_gen = payload.get("date_generated", datetime.now().strftime("%Y-%m-%d"))
    user_response = payload.get("user_response", "")
    action_status = payload.get("action_status", "")
    feedback_reason = payload.get("feedback_reason", "")
    valid_responses = ["helpful", "not_helpful", ""]
    if user_response and user_response not in valid_responses:
        return {"status": "error", "error": "Invalid user_response"}
    valid_statuses = ["completed", "in_progress", "not_now", "ignored", ""]
    if action_status and action_status not in valid_statuses:
        return {"status": "error", "error": "Invalid action_status"}
    result = _feedback_engine.submit_recommendation_feedback(
        business_id, environment, rec_id, rec_key, rec_type, source,
        date_gen, user_response, action_status, feedback_reason)
    if result.get("status") == "ok":
        _health_monitor.record_event("feedback", "rec_feedback_submitted", "INFO",
                                     "Feedback: " + user_response + "/" + action_status + " for " + rec_type)
    return result

@app.post("/api/v2/feedback/action-status")
def v2_update_action_status(payload: dict = None, x_api_key: str = None):
    check_auth(x_api_key)
    if not payload:
        return {"status": "error", "error": "No payload provided"}
    business_id, is_demo = _get_business_context()
    environment = "demo" if is_demo else "live"
    rec_id = payload.get("recommendation_id", "")
    action_status = payload.get("action_status", "")
    valid_statuses = ["completed", "in_progress", "not_now", "ignored"]
    if action_status not in valid_statuses:
        return {"status": "error", "error": "Invalid action_status"}
    return _feedback_engine.update_action_status(business_id, environment, rec_id, action_status)

@app.post("/api/v2/feedback/event")
def v2_record_recommendation_event(payload: dict = None, x_api_key: str = None):
    check_auth(x_api_key)
    if not payload:
        return {"status": "error", "error": "No payload provided"}
    business_id, is_demo = _get_business_context()
    environment = "demo" if is_demo else "live"
    rec_id = payload.get("recommendation_id", "")
    event_type = payload.get("event_type", "")
    rec_type = payload.get("recommendation_type", "")
    valid_events = ["viewed", "opened", "acted", "dismissed", "completed", "generated"]
    if event_type not in valid_events:
        return {"status": "error", "error": "Invalid event_type"}
    return _feedback_engine.record_recommendation_event(
        business_id, environment, rec_id, event_type, rec_type, payload.get("metadata"))

@app.post("/api/v2/feedback/feature")
def v2_submit_feature_feedback(payload: dict = None, x_api_key: str = None):
    check_auth(x_api_key)
    if not payload:
        return {"status": "error", "error": "No payload provided"}
    business_id, is_demo = _get_business_context()
    environment = "demo" if is_demo else "live"
    response_text = (payload.get("response_text") or "").strip()
    if not response_text:
        return {"status": "error", "error": "response_text is required"}
    if len(response_text) > 2000:
        return {"status": "error", "error": "response_text too long (max 2000 chars)"}
    return _feedback_engine.submit_feature_feedback(
        business_id, environment, response_text, payload.get("page_context", ""))

@app.post("/api/v2/feedback/satisfaction")
def v2_submit_satisfaction(payload: dict = None, x_api_key: str = None):
    check_auth(x_api_key)
    if not payload:
        return {"status": "error", "error": "No payload provided"}
    business_id, is_demo = _get_business_context()
    environment = "demo" if is_demo else "live"
    rating = payload.get("rating", "")
    prompt_context = payload.get("prompt_context", "")
    return _feedback_engine.submit_satisfaction(business_id, environment, rating, prompt_context)

@app.get("/api/v2/feedback/satisfaction-prompt")
def v2_check_satisfaction_prompt(x_api_key: str = None):
    check_auth(x_api_key)
    business_id, is_demo = _get_business_context()
    environment = "demo" if is_demo else "live"
    should_show = _feedback_engine.should_show_satisfaction_prompt(business_id, environment)
    if should_show:
        _feedback_engine.mark_satisfaction_shown(business_id, environment)
    return {"should_show": should_show}

@app.get("/api/v2/feedback/recommendation-key")
def v2_get_recommendation_key(source: str = "", rec_type: str = "",
                              target_type: str = "", target_id: str = "",
                              action_slug: str = "", x_api_key: str = None):
    check_auth(x_api_key)
    business_id, is_demo = _get_business_context()
    environment = "demo" if is_demo else "live"
    date_gen = datetime.now().strftime("%Y-%m-%d")
    rec_key = FeedbackEngine.generate_recommendation_key(
        business_id, environment, source, rec_type, target_type, target_id, action_slug)
    rec_id = FeedbackEngine.generate_recommendation_id(rec_key, date_gen)
    return {"recommendation_key": rec_key, "recommendation_id": rec_id, "date_generated": date_gen}

# ---- ADMIN FEEDBACK ENDPOINTS ----

@app.get("/api/admin/feedback/report")
def admin_feedback_report(x_admin_key: str = Header(default="", alias="X-Admin-Key"),
                          business_id: str = None, environment: str = None):
    check_admin_auth(x_admin_key)
    report = _feedback_engine.get_admin_feedback_report(business_id, environment)
    _health_monitor.record_admin_action("admin", "view_feedback_report", "feedback", "ok")
    return report

@app.get("/api/admin/feedback/events")
def admin_feedback_events(x_admin_key: str = Header(default="", alias="X-Admin-Key"),
                          business_id: str = None, environment: str = None):
    check_admin_auth(x_admin_key)
    return _feedback_engine.get_event_stats(business_id, environment)

@app.get("/api/admin/feedback/recent")
def admin_feedback_recent(x_admin_key: str = Header(default="", alias="X-Admin-Key"),
                          limit: int = 50):
    check_admin_auth(x_admin_key)
    return {"feedback": _feedback_engine.get_recent_feedback(limit)}

''' + marker

if marker in code:
    code = code.replace(marker, feedback_block, 1)
    print("2. Added feedback endpoints + admin feedback endpoints")
else:
    print("ERROR: ADMIN ENDPOINTS marker not found")

with open('/home/user/workspace/command-center/server.py', 'w') as f:
    f.write(code)
print("Done")
