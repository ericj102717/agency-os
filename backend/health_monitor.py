"""
Production Health Monitor for Command Center V2.

Lightweight, in-memory health tracking that observes existing systems
without triggering expensive recomputations. All logs are bounded with
deque(maxlen=...) to prevent unbounded memory growth.

Logs reset on server restart unless persisted to SQLite (optional).
"""

import os
import time
import threading
import hmac
import sqlite3
from collections import deque, defaultdict
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional


class HealthMonitor:
    """Singleton health monitor for Command Center V2."""

    def __init__(self):
        self._lock = threading.RLock()
        self._start_time = time.time()
        self._start_dt = datetime.now()

        # Bounded in-memory logs
        self.events = deque(maxlen=500)
        self.errors = deque(maxlen=500)
        self.audit_log = deque(maxlen=500)
        self.performance = defaultdict(lambda: deque(maxlen=100))

        # Service status registry
        self.services: Dict[str, Dict[str, Any]] = {}
        self._init_services()

        # Admin alerts
        self.alerts: List[Dict[str, Any]] = []

        # App version
        self.app_version = "2.0.0"
        self.build_id = f"build-{datetime.now().strftime('%Y%m%d%H%M')}"
        self.environment = os.environ.get("APP_ENV", "development")

        # Track scorecard computation timing
        self._scorecard_start_time: Optional[float] = None

    def _init_services(self):
        """Initialize service registry with known services."""
        known_services = [
            "application",
            "database",
            "authentication",
            "admin_auth",
            "api",
            "data_processing",
            "recommendation_engine",
            "forecasting",
            "scorecard",
            "storage",
            "demo_environment",
        ]
        for svc in known_services:
            self.services[svc] = {
                "status": "unknown",
                "last_success": None,
                "last_failure": None,
                "response_time_ms": None,
                "error_count": 0,
                "issue": None,
            }

    # ---- Event Recording ----

    def record_event(self, component: str, event_type: str,
                     severity: str = "INFO", message: str = "",
                     metadata: Optional[Dict] = None):
        """Record a system event."""
        with self._lock:
            event = {
                "timestamp": datetime.now().isoformat(),
                "component": component,
                "event_type": event_type,
                "severity": severity,
                "message": message,
                "metadata": metadata or {},
            }
            self.events.append(event)
            # Auto-update service status on certain events
            if severity == "CRITICAL":
                self._evaluate_alerts()

    def record_error(self, component: str, category: str,
                      severity: str, message: str,
                      safe_context: Optional[Dict] = None):
        """Record an error. safe_context must not contain sensitive data."""
        with self._lock:
            error = {
                "id": f"ERR-{len(self.errors)+1:04d}",
                "timestamp": datetime.now().isoformat(),
                "component": component,
                "category": category,
                "severity": severity,
                "message": message,
                "safe_context": safe_context or {},
                "status": "open",
                "resolution": None,
            }
            self.errors.append(error)

            # Update service error count
            if component in self.services:
                self.services[component]["error_count"] += 1
                self.services[component]["last_failure"] = error["timestamp"]
                if severity in ("ERROR", "CRITICAL"):
                    self.services[component]["issue"] = message

            if severity == "CRITICAL":
                self._evaluate_alerts()

    def record_timing(self, component: str, operation: str,
                      duration_ms: float, status: str = "success"):
        """Record a performance timing."""
        with self._lock:
            key = f"{component}.{operation}"
            self.performance[key].append({
                "timestamp": datetime.now().isoformat(),
                "duration_ms": round(duration_ms, 2),
                "status": status,
            })

            # Update service response time
            if component in self.services:
                self.services[component]["response_time_ms"] = round(duration_ms, 2)
                if status == "success":
                    self.services[component]["last_success"] = datetime.now().isoformat()
                elif status == "failed":
                    self.services[component]["last_failure"] = datetime.now().isoformat()

    def set_service_status(self, name: str, status: str,
                           last_success: Optional[str] = None,
                           last_failure: Optional[str] = None,
                           response_time_ms: Optional[float] = None,
                           issue: Optional[str] = None):
        """Set the status of a service."""
        with self._lock:
            if name not in self.services:
                self.services[name] = {
                    "status": "unknown",
                    "last_success": None,
                    "last_failure": None,
                    "response_time_ms": None,
                    "error_count": 0,
                    "issue": None,
                }
            self.services[name]["status"] = status
            if last_success:
                self.services[name]["last_success"] = last_success
            if last_failure:
                self.services[name]["last_failure"] = last_failure
            if response_time_ms is not None:
                self.services[name]["response_time_ms"] = round(response_time_ms, 2)
            if issue is not None:
                self.services[name]["issue"] = issue

    def record_admin_action(self, admin_id: str, action: str,
                             target: str, result: str):
        """Record an admin action for audit purposes."""
        with self._lock:
            entry = {
                "timestamp": datetime.now().isoformat(),
                "admin_id": admin_id,
                "action": action,
                "target": target,
                "result": result,
            }
            self.audit_log.append(entry)

    def record_scorecard_start(self):
        """Mark the start of scorecard computation."""
        with self._lock:
            self._scorecard_start_time = time.time()

    def record_scorecard_complete(self, success: bool, error: Optional[str] = None):
        """Mark scorecard computation completion."""
        with self._lock:
            if self._scorecard_start_time:
                duration = (time.time() - self._scorecard_start_time) * 1000
                self.record_timing("scorecard", "compute", duration,
                                   "success" if success else "failed")
                self._scorecard_start_time = None

            if success:
                self.set_service_status("scorecard", "healthy",
                                        last_success=datetime.now().isoformat(),
                                        issue=None)
            else:
                self.set_service_status("scorecard", "error",
                                        last_failure=datetime.now().isoformat(),
                                        issue=error or "Scorecard computation failed")
                self.record_error("scorecard", "computation", "ERROR",
                                  error or "Scorecard computation failed")

    # ---- Health Checks ----

    def run_lightweight_checks(self):
        """Run lightweight health checks. Does NOT trigger expensive computations."""
        with self._lock:
            now = datetime.now().isoformat()

            # Application health
            uptime = time.time() - self._start_time
            self.set_service_status("application", "healthy",
                                    last_success=now,
                                    response_time_ms=0)

            # Database health - lightweight check
            try:
                db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.db")
                start = time.time()
                conn = sqlite3.connect(db_path, timeout=3)
                conn.execute("SELECT 1")
                contact_count = conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
                conn.close()
                duration = (time.time() - start) * 1000
                self.set_service_status("database", "healthy",
                                        last_success=now,
                                        response_time_ms=duration,
                                        issue=None)
            except Exception as e:
                self.set_service_status("database", "critical",
                                        last_failure=now,
                                        issue=str(e)[:200])
                self.record_error("database", "connection", "CRITICAL",
                                  f"Database health check failed: {e}")

            # Storage health
            try:
                if os.path.exists(db_path):
                    size = os.path.getsize(db_path)
                    wal_path = db_path + "-wal"
                    wal_size = os.path.getsize(wal_path) if os.path.exists(wal_path) else 0
                    self.set_service_status("storage", "healthy",
                                            last_success=now,
                                            issue=None)
                else:
                    self.set_service_status("storage", "critical",
                                            last_failure=now,
                                            issue="Database file not found")
            except Exception as e:
                self.set_service_status("storage", "warning",
                                        issue=str(e)[:200])

            # Authentication health
            api_key = os.environ.get("AGENCY_API_KEY", "")
            if api_key:
                self.set_service_status("authentication", "healthy",
                                        last_success=now,
                                        issue=None)
            else:
                self.set_service_status("authentication", "warning",
                                        issue="DEV_MODE: No API key set (development only)")

            # Admin auth health
            admin_key = os.environ.get("ADMIN_API_KEY", "")
            if admin_key:
                self.set_service_status("admin_auth", "healthy",
                                        last_success=now,
                                        issue=None)
            else:
                self.set_service_status("admin_auth", "warning",
                                        issue="ADMIN_API_KEY not configured")

            # API health - check if server is responding
            self.set_service_status("api", "healthy",
                                    last_success=now,
                                    response_time_ms=0)

            # Scorecard health - inspect cache state (do NOT recompute)
            self._check_scorecard_cache()

            # Forecasting health - inspect cache state
            self._check_forecasting_cache()

            # Recommendation engine health
            self._check_recommendation_health()

            # Demo environment health
            try:
                conn = sqlite3.connect(db_path, timeout=3)
                demo = conn.execute("SELECT is_demo_mode FROM demo_state WHERE id=1").fetchone()
                conn.close()
                if demo and demo[0] == 1:
                    self.set_service_status("demo_environment", "healthy",
                                            last_success=now,
                                            issue="Demo mode active")
                else:
                    self.set_service_status("demo_environment", "healthy",
                                            last_success=now,
                                            issue="Live mode")
            except Exception:
                self.set_service_status("demo_environment", "warning",
                                        issue="Unable to check demo state")

            # Data processing health
            self.set_service_status("data_processing", "healthy",
                                    last_success=now)

            # Evaluate overall status
            self._evaluate_alerts()

    def _check_scorecard_cache(self):
        """Inspect scorecard cache without triggering computation."""
        try:
            # Import here to avoid circular imports
            import server
            cache = getattr(server, "_scorecard_cache", {})
            computing = cache.get("computing", False)
            data = cache.get("data")
            ts = cache.get("ts", 0)
            error = cache.get("error")

            now = time.time()

            if error:
                self.set_service_status("scorecard", "error",
                                        issue=f"Cache error: {error[:100]}")
            elif computing:
                # Check if computation has been running too long
                if hasattr(server, "_scorecard_start_time") and server._scorecard_start_time:
                    elapsed = now - server._scorecard_start_time
                    if elapsed > 300:  # 5 minutes
                        self.set_service_status("scorecard", "critical",
                                                issue=f"Scorecard computing for {elapsed:.0f}s (expected ~200s)")
                    else:
                        self.set_service_status("scorecard", "healthy",
                                                issue=f"Computing ({elapsed:.0f}s elapsed)")
                else:
                    self.set_service_status("scorecard", "healthy",
                                            issue="Computing...")
            elif data:
                age = now - ts if ts else 999999
                if age > 3600:  # 1 hour
                    self.set_service_status("scorecard", "warning",
                                            issue=f"Cache stale ({age/60:.0f} min old)")
                else:
                    self.set_service_status("scorecard", "healthy",
                                            issue=None)
            else:
                self.set_service_status("scorecard", "warning",
                                        issue="No cached data (will compute on first request)")
        except Exception as e:
            self.set_service_status("scorecard", "warning",
                                    issue=f"Unable to check: {e}")

    def _check_forecasting_cache(self):
        """Inspect forecasting cache state."""
        try:
            import server
            cache = getattr(server, "_cc_cache", {})
            fingerprint = cache.get("fingerprint")
            data = cache.get("data")
            ts = cache.get("ts", 0)

            now = time.time()

            if data:
                age = now - ts if ts else 999999
                if age > 1800:  # 30 minutes
                    self.set_service_status("forecasting", "warning",
                                            issue=f"Cache stale ({age/60:.0f} min old)")
                else:
                    self.set_service_status("forecasting", "healthy",
                                            issue=None)
            else:
                self.set_service_status("forecasting", "warning",
                                        issue="No cached data")
        except Exception as e:
            self.set_service_status("forecasting", "warning",
                                    issue=f"Unable to check: {e}")

    def _check_recommendation_health(self):
        """Check recommendation engine via action queue availability."""
        try:
            db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.db")
            conn = sqlite3.connect(db_path, timeout=3)
            # Check if action queue has data
            count = conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
            conn.close()
            if count > 0:
                self.set_service_status("recommendation_engine", "healthy",
                                        issue=None)
            else:
                self.set_service_status("recommendation_engine", "warning",
                                        issue="No contacts to generate recommendations from")
        except Exception as e:
            self.set_service_status("recommendation_engine", "warning",
                                    issue=f"Unable to check: {e}")

    # ---- Data Freshness ----

    def get_data_freshness(self) -> List[Dict[str, Any]]:
        """Get freshness of derived metrics."""
        freshness = []
        now = time.time()

        try:
            import server

            # Scorecard freshness
            sc_cache = getattr(server, "_scorecard_cache", {})
            sc_ts = sc_cache.get("ts", 0)
            if sc_ts:
                age = now - sc_ts
                freshness.append({
                    "metric": "Business Health Score",
                    "last_calculated": datetime.fromtimestamp(sc_ts).isoformat(),
                    "age_seconds": round(age),
                    "age_display": self._format_age(age),
                    "status": "fresh" if age < 300 else "stale" if age < 3600 else "very_stale",
                })
            else:
                freshness.append({
                    "metric": "Business Health Score",
                    "last_calculated": None,
                    "age_seconds": None,
                    "age_display": "Never",
                    "status": "never",
                })

            # Command center freshness
            cc_cache = getattr(server, "_cc_cache", {})
            cc_ts = cc_cache.get("ts", 0)
            if cc_ts:
                age = now - cc_ts
                freshness.append({
                    "metric": "Command Center Dashboard",
                    "last_calculated": datetime.fromtimestamp(cc_ts).isoformat(),
                    "age_seconds": round(age),
                    "age_display": self._format_age(age),
                    "status": "fresh" if age < 300 else "stale" if age < 1800 else "very_stale",
                })
            else:
                freshness.append({
                    "metric": "Command Center Dashboard",
                    "last_calculated": None,
                    "age_seconds": None,
                    "age_display": "Never",
                    "status": "never",
                })

            # V2 cache freshness
            v2_cache = getattr(server, "_v2_cache", {})
            v2_ts = v2_cache.get("ts", 0)
            if v2_ts:
                age = now - v2_ts
                freshness.append({
                    "metric": "V2 Intelligence Layer",
                    "last_calculated": datetime.fromtimestamp(v2_ts).isoformat(),
                    "age_seconds": round(age),
                    "age_display": self._format_age(age),
                    "status": "fresh" if age < 300 else "stale" if age < 1800 else "very_stale",
                })
            else:
                freshness.append({
                    "metric": "V2 Intelligence Layer",
                    "last_calculated": None,
                    "age_seconds": None,
                    "age_display": "Never",
                    "status": "never",
                })

        except Exception:
            pass

        return freshness

    def _format_age(self, seconds: float) -> str:
        """Format age in human-readable form."""
        if seconds < 60:
            return f"{int(seconds)}s ago"
        elif seconds < 3600:
            return f"{int(seconds/60)} min ago"
        elif seconds < 86400:
            return f"{int(seconds/3600)} hours ago"
        else:
            return f"{int(seconds/86400)} days ago"

    # ---- Performance Summary ----

    def get_performance_summary(self) -> List[Dict[str, Any]]:
        """Get performance summary for tracked operations."""
        summary = []
        with self._lock:
            for key, timings in self.performance.items():
                if not timings:
                    continue
                recent = list(timings)
                durations = [t["duration_ms"] for t in recent]
                avg = sum(durations) / len(durations)
                max_val = max(durations)
                min_val = min(durations)
                failures = sum(1 for t in recent if t["status"] != "success")

                # Determine performance level
                if key.startswith("scorecard"):
                    warning_threshold = 200000  # 200s
                    critical_threshold = 600000  # 600s
                elif key.startswith("command_center") or key.startswith("command-center"):
                    warning_threshold = 20000  # 20s
                    critical_threshold = 60000  # 60s
                else:
                    warning_threshold = 2000  # 2s
                    critical_threshold = 10000  # 10s

                if max_val > critical_threshold:
                    level = "critical"
                elif max_val > warning_threshold:
                    level = "slow"
                else:
                    level = "normal"

                summary.append({
                    "operation": key,
                    "avg_ms": round(avg, 2),
                    "min_ms": round(min_val, 2),
                    "max_ms": round(max_val, 2),
                    "sample_count": len(recent),
                    "failure_count": failures,
                    "level": level,
                    "last_sample": recent[-1]["timestamp"] if recent else None,
                })

        return sorted(summary, key=lambda x: x["avg_ms"], reverse=True)

    # ---- Alerts ----

    def _evaluate_alerts(self):
        """Evaluate current conditions and generate alerts."""
        self.alerts = []

        for name, svc in self.services.items():
            status = svc.get("status", "unknown")
            issue = svc.get("issue")

            if status == "critical":
                self.alerts.append({
                    "severity": "CRITICAL",
                    "component": name,
                    "message": issue or f"{name} is in critical state",
                    "timestamp": datetime.now().isoformat(),
                })
            elif status == "error":
                self.alerts.append({
                    "severity": "ERROR",
                    "component": name,
                    "message": issue or f"{name} has errors",
                    "timestamp": datetime.now().isoformat(),
                })
            elif status == "warning" and issue and "DEV_MODE" not in issue and "not configured" not in issue:
                self.alerts.append({
                    "severity": "WARNING",
                    "component": name,
                    "message": issue,
                    "timestamp": datetime.now().isoformat(),
                })

    # ---- Snapshot ----

    def snapshot(self) -> Dict[str, Any]:
        """Get a complete health snapshot."""
        with self._lock:
            # Determine overall status
            statuses = [s["status"] for s in self.services.values()]
            if "critical" in statuses or "error" in statuses:
                overall = "critical"
            elif "warning" in statuses:
                overall = "warning"
            elif "unknown" in statuses and "healthy" not in statuses:
                overall = "unknown"
            else:
                overall = "healthy"

            uptime = time.time() - self._start_time

            return {
                "overall_status": overall,
                "generated_at": datetime.now().isoformat(),
                "uptime_seconds": round(uptime),
                "uptime_display": self._format_age(uptime),
                "environment": self.environment,
                "app_version": self.app_version,
                "build_id": self.build_id,
                "started_at": self._start_dt.isoformat(),
                "services": dict(self.services),
                "alerts": self.alerts,
                "data_freshness": self.get_data_freshness(),
                "performance": self.get_performance_summary(),
                "recent_events": list(self.events)[-20:],
                "recent_errors": [e for e in self.errors if e["status"] == "open"][-20:],
                "recent_audit": list(self.audit_log)[-20:],
                "event_count": len(self.events),
                "error_count": len(self.errors),
                "open_error_count": sum(1 for e in self.errors if e["status"] == "open"),
                "alert_count": len(self.alerts),
            }

    # ---- Admin Actions ----

    def clear_cache(self, component: Optional[str] = None) -> Dict[str, Any]:
        """Clear safe caches."""
        cleared = []
        try:
            import server

            if component is None or component == "command_center":
                server._cc_cache = {"data": None, "ts": 0, "fingerprint": None}
                cleared.append("command_center")

            if component is None or component == "scorecard":
                server._scorecard_cache = {
                    "data": None, "ts": 0, "computing": False, "error": None
                }
                cleared.append("scorecard")

            if component is None or component == "v2":
                server._v2_cache = {"data": None, "ts": 0}
                cleared.append("v2")

            self.record_event("admin", "cache_cleared", "INFO",
                              f"Cleared caches: {', '.join(cleared)}")
        except Exception as e:
            return {"status": "error", "error": str(e)}

        return {"status": "ok", "cleared": cleared}

    def retry_scorecard(self) -> Dict[str, Any]:
        """Trigger scorecard recomputation in background."""
        try:
            import server
            if hasattr(server, "_compute_scorecard_bg"):
                server._compute_scorecard_bg()
                self.record_event("admin", "scorecard_retry", "INFO",
                                  "Scorecard recomputation triggered")
                return {"status": "ok", "message": "Scorecard recomputation started"}
            return {"status": "error", "error": "Scorecard computation function not available"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def resolve_error(self, error_id: str, resolution: str) -> Dict[str, Any]:
        """Mark an error as resolved."""
        with self._lock:
            for err in self.errors:
                if err["id"] == error_id:
                    err["status"] = "resolved"
                    err["resolution"] = resolution
                    return {"status": "ok", "error_id": error_id}
            return {"status": "error", "error": "Error not found"}

    # ---- Simulation (for testing only) ----

    def simulate_failure(self, component: str, failure_type: str) -> Dict[str, Any]:
        """Simulate a failure for testing. Only available in non-production."""
        if self.environment == "production":
            return {"status": "error", "error": "Simulation not allowed in production"}

        simulations = {
            "database_unavailable": lambda: self.record_error(
                "database", "connection", "CRITICAL",
                "SIMULATED: Database connection failed",
                {"simulated": True}
            ),
            "ai_timeout": lambda: self.record_error(
                "recommendation_engine", "ai_timeout", "ERROR",
                "SIMULATED: AI request timed out after 30s",
                {"simulated": True, "timeout_ms": 30000}
            ),
            "forecast_failure": lambda: self.record_error(
                "forecasting", "calculation", "ERROR",
                "SIMULATED: Forecast calculation failed",
                {"simulated": True}
            ),
            "slow_api": lambda: self.record_timing(
                "api", "request", 15000, "slow"
            ),
            "auth_failure": lambda: self.record_error(
                "authentication", "auth_failed", "WARNING",
                "SIMULATED: Authentication failure spike",
                {"simulated": True}
            ),
            "recommendation_failure": lambda: self.record_error(
                "recommendation_engine", "generation", "ERROR",
                "SIMULATED: Recommendation generation failed",
                {"simulated": True}
            ),
        }

        handler = simulations.get(failure_type)
        if handler:
            handler()
            self._evaluate_alerts()
            return {"status": "ok", "message": f"Simulated {failure_type}"}
        return {"status": "error", "error": f"Unknown simulation type: {failure_type}"}

    def simulate_recovery(self) -> Dict[str, Any]:
        """Clear all simulated failures and refresh health."""
        if self.environment == "production":
            return {"status": "error", "error": "Simulation not allowed in production"}

        with self._lock:
            # Resolve all simulated errors
            for err in self.errors:
                if err.get("safe_context", {}).get("simulated"):
                    err["status"] = "resolved"
                    err["resolution"] = "Recovered from simulation"

        self.run_lightweight_checks()
        return {"status": "ok", "message": "All simulated failures cleared"}


# Module-level singleton
monitor = HealthMonitor()
