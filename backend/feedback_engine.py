"""
User Feedback & Recommendation Learning System for Command Center V2.

Lightweight, SQLite-backed feedback collection that tracks recommendation
quality, action outcomes, and customer satisfaction without slowing
the main application.

All logs are bounded. Account isolation enforced via business_id + environment.
No sensitive business data stored. No automatic recommendation retraining.
"""

import os
import sqlite3
import hashlib
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional


class FeedbackEngine:
    """SQLite-backed feedback and recommendation learning engine."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_tables()

    def _conn(self):
        conn = sqlite3.connect(self.db_path, timeout=5)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=3000")
        return conn

    def _init_tables(self):
        """Create feedback tables if they don't exist."""
        conn = self._conn()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS recommendation_feedback_v2 (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    business_id TEXT NOT NULL,
                    environment TEXT NOT NULL,
                    recommendation_id TEXT NOT NULL,
                    recommendation_key TEXT NOT NULL,
                    recommendation_type TEXT DEFAULT '',
                    source TEXT DEFAULT '',
                    date_generated TEXT DEFAULT '',
                    user_response TEXT DEFAULT '',
                    action_status TEXT DEFAULT '',
                    feedback_reason TEXT DEFAULT '',
                    quality_score TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(business_id, environment, recommendation_id)
                );

                CREATE TABLE IF NOT EXISTS recommendation_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    business_id TEXT NOT NULL,
                    environment TEXT NOT NULL,
                    recommendation_id TEXT NOT NULL,
                    recommendation_type TEXT DEFAULT '',
                    event_type TEXT NOT NULL,
                    metadata TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS feature_feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    business_id TEXT NOT NULL,
                    environment TEXT NOT NULL,
                    page_context TEXT DEFAULT '',
                    response_text TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS satisfaction_feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    business_id TEXT NOT NULL,
                    environment TEXT NOT NULL,
                    rating TEXT NOT NULL,
                    prompt_context TEXT DEFAULT '',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS feedback_prompt_state (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    business_id TEXT NOT NULL,
                    environment TEXT NOT NULL,
                    prompt_key TEXT NOT NULL,
                    last_shown_at TEXT,
                    last_response_at TEXT,
                    shown_count INTEGER DEFAULT 0,
                    UNIQUE(business_id, environment, prompt_key)
                );

                CREATE INDEX IF NOT EXISTS idx_rf2_business
                    ON recommendation_feedback_v2(business_id, environment);
                CREATE INDEX IF NOT EXISTS idx_rf2_type
                    ON recommendation_feedback_v2(recommendation_type);
                CREATE INDEX IF NOT EXISTS idx_re_business
                    ON recommendation_events(business_id, environment);
                CREATE INDEX IF NOT EXISTS idx_re_type
                    ON recommendation_events(event_type);
                CREATE INDEX IF NOT EXISTS idx_ff_business
                    ON feature_feedback(business_id, environment);
                CREATE INDEX IF NOT EXISTS idx_sf_business
                    ON satisfaction_feedback(business_id, environment);
                CREATE INDEX IF NOT EXISTS idx_fps_business
                    ON feedback_prompt_state(business_id, environment);
            """)
            conn.commit()
        finally:
            conn.close()

    # ---- Recommendation ID Generation ----

    @staticmethod
    def generate_recommendation_key(business_id: str, environment: str,
                                     source: str, rec_type: str,
                                     target_type: str, target_id: str,
                                     action_slug: str) -> str:
        """Generate stable recommendation key for repeat appearances."""
        raw = f"v1|{business_id}|{environment}|{source}|{rec_type}|{target_type}|{target_id}|{action_slug}"
        return hashlib.sha256(raw.encode()).hexdigest()[:20]

    @staticmethod
    def generate_recommendation_id(rec_key: str, generated_date: str) -> str:
        """Generate instance-specific recommendation ID."""
        raw = f"{rec_key}|{generated_date}"
        return hashlib.sha256(raw.encode()).hexdigest()[:20]

    # ---- Feedback Submission ----

    def submit_recommendation_feedback(self, business_id: str, environment: str,
                                        recommendation_id: str, recommendation_key: str,
                                        recommendation_type: str = "",
                                        source: str = "",
                                        date_generated: str = "",
                                        user_response: str = "",
                                        action_status: str = "",
                                        feedback_reason: str = "") -> Dict[str, Any]:
        """Submit or update recommendation feedback."""
        now = datetime.now().isoformat()
        quality_score = self._compute_quality_score(user_response, action_status)

        conn = self._conn()
        try:
            conn.execute("""
                INSERT INTO recommendation_feedback_v2
                    (business_id, environment, recommendation_id, recommendation_key,
                     recommendation_type, source, date_generated,
                     user_response, action_status, feedback_reason,
                     quality_score, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(business_id, environment, recommendation_id)
                DO UPDATE SET
                    user_response = excluded.user_response,
                    action_status = excluded.action_status,
                    feedback_reason = excluded.feedback_reason,
                    quality_score = excluded.quality_score,
                    updated_at = excluded.updated_at
            """, (business_id, environment, recommendation_id, recommendation_key,
                  recommendation_type, source, date_generated,
                  user_response, action_status, feedback_reason,
                  quality_score, now, now))
            conn.commit()
            return {"status": "ok", "quality_score": quality_score}
        except Exception as e:
            return {"status": "error", "error": str(e)}
        finally:
            conn.close()

    def _compute_quality_score(self, user_response: str, action_status: str) -> str:
        """Compute internal quality score (not exposed to business owners)."""
        if user_response == "helpful" and action_status == "completed":
            return "high"
        elif user_response == "helpful" and action_status in ("in_progress", ""):
            return "medium"
        elif action_status == "ignored" or user_response == "not_helpful":
            return "poor"
        elif action_status == "not_now":
            return "low"
        elif user_response == "helpful":
            return "medium"
        return "unrated"

    # ---- Action Status Update ----

    def update_action_status(self, business_id: str, environment: str,
                              recommendation_id: str, action_status: str) -> Dict[str, Any]:
        """Update action status for a recommendation."""
        now = datetime.now().isoformat()
        quality_score = self._compute_quality_score("", action_status)

        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT user_response FROM recommendation_feedback_v2 WHERE business_id=? AND environment=? AND recommendation_id=?",
                (business_id, environment, recommendation_id)
            ).fetchone()

            if existing:
                user_resp = existing["user_response"] if existing["user_response"] else ""
                quality_score = self._compute_quality_score(user_resp, action_status)
                conn.execute("""
                    UPDATE recommendation_feedback_v2
                    SET action_status=?, quality_score=?, updated_at=?
                    WHERE business_id=? AND environment=? AND recommendation_id=?
                """, (action_status, quality_score, now, business_id, environment, recommendation_id))
            else:
                # Create entry if it doesn't exist
                conn.execute("""
                    INSERT INTO recommendation_feedback_v2
                        (business_id, environment, recommendation_id, recommendation_key,
                         recommendation_type, source, date_generated,
                         user_response, action_status, feedback_reason,
                         quality_score, created_at, updated_at)
                    VALUES (?, ?, ?, '', '', '', '', '', ?, '', ?, ?, ?)
                """, (business_id, environment, recommendation_id,
                      action_status, quality_score, now, now))

            conn.commit()
            return {"status": "ok", "quality_score": quality_score}
        except Exception as e:
            return {"status": "error", "error": str(e)}
        finally:
            conn.close()

    # ---- Recommendation Events ----

    def record_recommendation_event(self, business_id: str, environment: str,
                                     recommendation_id: str, event_type: str,
                                     recommendation_type: str = "",
                                     metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """Record a recommendation behavior event."""
        now = datetime.now().isoformat()
        safe_meta = json.dumps(metadata or {})[:500]  # Bounded

        conn = self._conn()
        try:
            conn.execute("""
                INSERT INTO recommendation_events
                    (business_id, environment, recommendation_id, recommendation_type,
                     event_type, metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (business_id, environment, recommendation_id, recommendation_type,
                  event_type, safe_meta, now))
            conn.commit()
            return {"status": "ok"}
        except Exception as e:
            return {"status": "error", "error": str(e)}
        finally:
            conn.close()

    # ---- Feature Feedback ----

    def submit_feature_feedback(self, business_id: str, environment: str,
                                 response_text: str, page_context: str = "") -> Dict[str, Any]:
        """Submit general product feedback."""
        now = datetime.now().isoformat()
        # Truncate to prevent abuse
        safe_text = response_text[:2000]

        conn = self._conn()
        try:
            conn.execute("""
                INSERT INTO feature_feedback
                    (business_id, environment, page_context, response_text, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (business_id, environment, page_context, safe_text, now))
            conn.commit()
            return {"status": "ok"}
        except Exception as e:
            return {"status": "error", "error": str(e)}
        finally:
            conn.close()

    # ---- Satisfaction Survey ----

    def submit_satisfaction(self, business_id: str, environment: str,
                              rating: str, prompt_context: str = "") -> Dict[str, Any]:
        """Submit satisfaction rating."""
        now = datetime.now().isoformat()
        valid_ratings = ["very_helpful", "helpful", "neutral", "not_helpful"]
        if rating not in valid_ratings:
            return {"status": "error", "error": f"Invalid rating. Must be one of: {valid_ratings}"}

        conn = self._conn()
        try:
            conn.execute("""
                INSERT INTO satisfaction_feedback
                    (business_id, environment, rating, prompt_context, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (business_id, environment, rating, prompt_context, now))
            conn.commit()

            # Update prompt state
            self._update_prompt_state(business_id, environment, "satisfaction", responded=True)
            return {"status": "ok"}
        except Exception as e:
            return {"status": "error", "error": str(e)}
        finally:
            conn.close()

    # ---- Prompt State (Fatigue Rules) ----

    def _update_prompt_state(self, business_id: str, environment: str,
                              prompt_key: str, shown: bool = False,
                              responded: bool = False):
        """Update feedback prompt state for fatigue rules."""
        now = datetime.now().isoformat()
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id, shown_count FROM feedback_prompt_state WHERE business_id=? AND environment=? AND prompt_key=?",
                (business_id, environment, prompt_key)
            ).fetchone()

            if existing:
                if shown:
                    conn.execute("""
                        UPDATE feedback_prompt_state
                        SET last_shown_at=?, shown_count=shown_count+1
                        WHERE id=?
                    """, (now, existing["id"]))
                if responded:
                    conn.execute("""
                        UPDATE feedback_prompt_state
                        SET last_response_at=?
                        WHERE id=?
                    """, (now, existing["id"]))
            else:
                conn.execute("""
                    INSERT INTO feedback_prompt_state
                        (business_id, environment, prompt_key,
                         last_shown_at, last_response_at, shown_count)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (business_id, environment, prompt_key,
                      now if shown else None,
                      now if responded else None,
                      1 if shown else 0))
            conn.commit()
        finally:
            conn.close()

    def should_show_satisfaction_prompt(self, business_id: str, environment: str) -> bool:
        """Determine if satisfaction prompt should be shown."""
        conn = self._conn()
        try:
            # Check if user has meaningful usage (at least 3 recommendation events)
            event_count = conn.execute(
                "SELECT COUNT(*) as cnt FROM recommendation_events WHERE business_id=? AND environment=?",
                (business_id, environment)
            ).fetchone()["cnt"]

            if event_count < 3:
                return False

            # Check prompt state
            state = conn.execute(
                "SELECT last_shown_at, last_response_at FROM feedback_prompt_state WHERE business_id=? AND environment=? AND prompt_key='satisfaction'",
                (business_id, environment)
            ).fetchone()

            now = datetime.now()
            if state:
                # If responded recently, don't show again for 7 days
                if state["last_response_at"]:
                    last_response = datetime.fromisoformat(state["last_response_at"])
                    if (now - last_response).days < 7:
                        return False
                # If shown but not responded, wait 1 day
                if state["last_shown_at"] and not state["last_response_at"]:
                    last_shown = datetime.fromisoformat(state["last_shown_at"])
                    if (now - last_shown).days < 1:
                        return False

            return True
        finally:
            conn.close()

    def mark_satisfaction_shown(self, business_id: str, environment: str):
        """Mark satisfaction prompt as shown."""
        self._update_prompt_state(business_id, environment, "satisfaction", shown=True)

    # ---- Admin Reports ----

    def get_admin_feedback_report(self, business_id: Optional[str] = None,
                                   environment: Optional[str] = None) -> Dict[str, Any]:
        """Generate comprehensive feedback report for admins."""
        conn = self._conn()
        try:
            where_parts = []
            params = []
            if business_id:
                where_parts.append("business_id = ?")
                params.append(business_id)
            if environment:
                where_parts.append("environment = ?")
                params.append(environment)

            where_clause = " AND ".join(where_parts) if where_parts else "1=1"
            env_clause = " AND ".join(where_parts) if where_parts else "1=1"

            # Overall metrics
            total = conn.execute(
                f"SELECT COUNT(*) as cnt FROM recommendation_feedback_v2 WHERE {where_clause}",
                params
            ).fetchone()["cnt"]

            if total == 0:
                return {
                    "status": "ok",
                    "total_recommendations": 0,
                    "helpful_rate": 0,
                    "not_helpful_rate": 0,
                    "completion_rate": 0,
                    "ignore_rate": 0,
                    "in_progress_rate": 0,
                    "not_now_rate": 0,
                    "quality_distribution": {},
                    "by_recommendation_type": [],
                    "weak_categories": [],
                    "most_common_reasons": [],
                    "satisfaction_trend": [],
                    "feature_feedback_count": 0,
                    "message": "Not enough data yet."
                }

            helpful = conn.execute(
                f"SELECT COUNT(*) as cnt FROM recommendation_feedback_v2 WHERE {where_clause} AND user_response='helpful'",
                params
            ).fetchone()["cnt"]
            not_helpful = conn.execute(
                f"SELECT COUNT(*) as cnt FROM recommendation_feedback_v2 WHERE {where_clause} AND user_response='not_helpful'",
                params
            ).fetchone()["cnt"]
            completed = conn.execute(
                f"SELECT COUNT(*) as cnt FROM recommendation_feedback_v2 WHERE {where_clause} AND action_status='completed'",
                params
            ).fetchone()["cnt"]
            ignored = conn.execute(
                f"SELECT COUNT(*) as cnt FROM recommendation_feedback_v2 WHERE {where_clause} AND action_status='ignored'",
                params
            ).fetchone()["cnt"]
            in_progress = conn.execute(
                f"SELECT COUNT(*) as cnt FROM recommendation_feedback_v2 WHERE {where_clause} AND action_status='in_progress'",
                params
            ).fetchone()["cnt"]
            not_now = conn.execute(
                f"SELECT COUNT(*) as cnt FROM recommendation_feedback_v2 WHERE {where_clause} AND action_status='not_now'",
                params
            ).fetchone()["cnt"]

            # Quality distribution
            quality_rows = conn.execute(
                f"SELECT quality_score, COUNT(*) as cnt FROM recommendation_feedback_v2 WHERE {where_clause} GROUP BY quality_score",
                params
            ).fetchall()
            quality_dist = {row["quality_score"]: row["cnt"] for row in quality_rows}

            # By recommendation type
            type_rows = conn.execute(
                f"""SELECT recommendation_type,
                       COUNT(*) as total,
                       SUM(CASE WHEN user_response='helpful' THEN 1 ELSE 0 END) as helpful,
                       SUM(CASE WHEN user_response='not_helpful' THEN 1 ELSE 0 END) as not_helpful,
                       SUM(CASE WHEN action_status='completed' THEN 1 ELSE 0 END) as completed,
                       SUM(CASE WHEN action_status='ignored' THEN 1 ELSE 0 END) as ignored
                   FROM recommendation_feedback_v2
                   WHERE {where_clause} AND recommendation_type != ''
                   GROUP BY recommendation_type
                   ORDER BY total DESC""",
                params
            ).fetchall()
            by_type = [dict(r) for r in type_rows]

            # Weak categories (min 3 samples, high ignore/not_helpful rate)
            weak = []
            for t in by_type:
                if t["total"] >= 3:
                    bad_count = max(t["ignored"], t["not_helpful"])
                    ignore_rate = bad_count / t["total"]
                    completion_rate = t["completed"] / t["total"]
                    if ignore_rate > 0.5 or completion_rate < 0.2:
                        weak.append({
                            "category": t["recommendation_type"],
                            "total": t["total"],
                            "ignore_rate": round(ignore_rate * 100, 1),
                            "completion_rate": round(completion_rate * 100, 1),
                            "issue": "high_ignore" if ignore_rate > 0.5 else "low_completion"
                        })

            # Most common feedback reasons
            reason_rows = conn.execute(
                f"""SELECT feedback_reason, COUNT(*) as cnt
                   FROM recommendation_feedback_v2
                   WHERE {where_clause} AND feedback_reason != ''
                   GROUP BY feedback_reason
                   ORDER BY cnt DESC
                   LIMIT 10""",
                params
            ).fetchall()
            reasons = [dict(r) for r in reason_rows]

            # Satisfaction trend (last 30 days)
            satisfaction_rows = conn.execute(
                f"""SELECT date(created_at) as date, rating, COUNT(*) as cnt
                   FROM satisfaction_feedback
                   WHERE {env_clause if where_parts else '1=1'}
                   AND created_at >= date('now', '-30 days')
                   GROUP BY date(created_at), rating
                   ORDER BY date DESC""",
                params if where_parts else []
            ).fetchall()

            # Build trend by date
            trend_by_date = {}
            for r in satisfaction_rows:
                d = r["date"]
                if d not in trend_by_date:
                    trend_by_date[d] = {"date": d, "total": 0, "score": 0}
                trend_by_date[d]["total"] += r["cnt"]
                score_map = {"very_helpful": 2, "helpful": 1, "neutral": 0, "not_helpful": -1}
                trend_by_date[d]["score"] += score_map.get(r["rating"], 0) * r["cnt"]

            trend = list(trend_by_date.values())
            for t in trend:
                t["avg_score"] = round(t["score"] / t["total"], 2) if t["total"] > 0 else 0

            # Feature feedback count
            ff_count = conn.execute(
                f"SELECT COUNT(*) as cnt FROM feature_feedback WHERE {env_clause if where_parts else '1=1'}",
                params if where_parts else []
            ).fetchone()["cnt"]

            # Recent feature feedback
            ff_rows = conn.execute(
                f"""SELECT response_text, page_context, created_at
                   FROM feature_feedback
                   WHERE {env_clause if where_parts else '1=1'}
                   ORDER BY created_at DESC LIMIT 20""",
                params if where_parts else []
            ).fetchall()
            recent_ff = [dict(r) for r in ff_rows]

            # Top helpful categories
            most_helpful = sorted(
                [t for t in by_type if t["helpful"] > 0],
                key=lambda x: x["helpful"], reverse=True
            )[:5]

            # Top ignored categories
            most_ignored = sorted(
                [t for t in by_type if t["ignored"] > 0],
                key=lambda x: x["ignored"], reverse=True
            )[:5]

            return {
                "status": "ok",
                "total_recommendations": total,
                "helpful_count": helpful,
                "not_helpful_count": not_helpful,
                "completed_count": completed,
                "ignored_count": ignored,
                "in_progress_count": in_progress,
                "not_now_count": not_now,
                "helpful_rate": round(helpful / total * 100, 1) if total else 0,
                "not_helpful_rate": round(not_helpful / total * 100, 1) if total else 0,
                "completion_rate": round(completed / total * 100, 1) if total else 0,
                "ignore_rate": round(ignored / total * 100, 1) if total else 0,
                "in_progress_rate": round(in_progress / total * 100, 1) if total else 0,
                "not_now_rate": round(not_now / total * 100, 1) if total else 0,
                "quality_distribution": quality_dist,
                "by_recommendation_type": by_type,
                "weak_categories": weak,
                "most_helpful_categories": most_helpful,
                "most_completed_categories": sorted(
                    [t for t in by_type if t["completed"] > 0],
                    key=lambda x: x["completed"], reverse=True
                )[:5],
                "most_ignored_categories": most_ignored,
                "recommendation_volume": conn.execute(
                    "SELECT COUNT(DISTINCT recommendation_id) as cnt FROM recommendation_events WHERE " + where_clause.replace("business_id", "business_id"),
                    params
                ).fetchone()["cnt"] if where_parts else conn.execute(
                    "SELECT COUNT(DISTINCT recommendation_id) as cnt FROM recommendation_events"
                ).fetchone()["cnt"],
                "most_common_reasons": reasons,
                "satisfaction_trend": trend,
                "feature_feedback_count": ff_count,
                "recent_feature_feedback": recent_ff,
            }
        finally:
            conn.close()

    # ---- Recommendation Performance by Category ----

    def get_recommendation_performance(self, business_id: str, environment: str) -> List[Dict]:
        """Get per-category recommendation performance."""
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT recommendation_type,
                       COUNT(*) as total,
                       SUM(CASE WHEN user_response='helpful' THEN 1 ELSE 0 END) as helpful,
                       SUM(CASE WHEN user_response='not_helpful' THEN 1 ELSE 0 END) as not_helpful,
                       SUM(CASE WHEN action_status='completed' THEN 1 ELSE 0 END) as completed,
                       SUM(CASE WHEN action_status='ignored' THEN 1 ELSE 0 END) as ignored
                   FROM recommendation_feedback_v2
                   WHERE business_id=? AND environment=? AND recommendation_type != ''
                   GROUP BY recommendation_type
                   ORDER BY total DESC""",
                (business_id, environment)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ---- Behavior Event Stats ----

    def get_event_stats(self, business_id: Optional[str] = None,
                         environment: Optional[str] = None) -> Dict[str, Any]:
        """Get recommendation behavior event statistics."""
        conn = self._conn()
        try:
            where_parts = []
            params = []
            if business_id:
                where_parts.append("business_id = ?")
                params.append(business_id)
            if environment:
                where_parts.append("environment = ?")
                params.append(environment)

            where_clause = " AND ".join(where_parts) if where_parts else "1=1"

            rows = conn.execute(
                f"""SELECT event_type, COUNT(*) as cnt
                   FROM recommendation_events
                   WHERE {where_clause}
                   GROUP BY event_type
                   ORDER BY cnt DESC""",
                params
            ).fetchall()

            return {
                "event_counts": {row["event_type"]: row["cnt"] for row in rows},
                "total_events": sum(row["cnt"] for row in rows)
            }
        finally:
            conn.close()

    # ---- Recent Feedback (for admin) ----

    def get_recent_feedback(self, limit: int = 50) -> List[Dict]:
        """Get recent feedback entries (admin only)."""
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT * FROM recommendation_feedback_v2
                   ORDER BY updated_at DESC LIMIT ?""",
                (limit,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()


# Module-level singleton
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.db")
feedback_engine = FeedbackEngine(DB_PATH)
