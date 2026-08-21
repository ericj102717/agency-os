# Backend Module Audit

## Summary

| Metric | Count |
|---|---|
| Total .py files (before cleanup) | 97 |
| Runtime-reachable from server.py | 88 |
| Deleted (patch scripts) | 4 |
| Moved to backend/scripts/ (diagnostic/migration) | 5 |
| Wrapper stub modules | 6 |
| Total after cleanup | 88 backend/ + 5 scripts/ |

---

## Cleanup Actions Performed

### Deleted (one-off patch/hotfix scripts)
- `_fix.py` — empty placeholder
- `_fix_feedback.py` — one-time fix for feedback system bugs
- `_patch_frontend.py` — one-time patch to add feedback UI to old vanilla JS app.js
- `_patch_server.py` — one-time patch to old server.py at a different path

### Moved to backend/scripts/ (not runtime code)
- `migrate_to_postgres.py` — SQLite→Postgres migration (called by start-published.sh)
- `generate_test_data.py` — Generates test dataset via API calls
- `real_data_validation_harness.py` — Validates full intelligence pipeline
- `scorecard_test_harness.py` — Tests 8 scorecard scenarios
- `full_business_system_audit.py` — Tests all 12 agents + Command Center V2

### Dead code removed from server.py
- `safe_import()` function — defined but never called
- 10 unused imports: `_completed_types`, `_consolidate_dupes`, `_gen_action_card`, `_is_executable`, `_pending_follow_ups`, `_prepare_action_ctx`, `_snoozed_returning`, `defaultdict`, `get_agent_summaries`, `get_current_state`, `get_comparison_periods`, `timedelta`

---

## Module Inventory by Domain

### Core Infrastructure (4 files, ~1,200 lines)
| Module | Lines | Responsibility |
|---|---|---|
| `db.py` | 329 | Supabase Postgres connection pool, query helpers, init_db |
| `data_store.py` | 661 | Generic data access (contacts, opportunities, revenue) |
| `comm_store.py` | 595 | Communications storage (calls, texts, emails) |
| `calendar_oauth.py` | 646 | Google/Microsoft OAuth + calendar event sync |

### Server / API Layer (1 file, 3,831 lines)
| Module | Lines | Responsibility |
|---|---|---|
| `server.py` | 3,831 | FastAPI app, all API endpoints, routing, auth, health checks |

**Note:** server.py is a monolith. V3 should split into route modules (e.g., `routes/summary.py`, `routes/actions.py`, `routes/calendar.py`).

### Intelligence Backend (2 files, ~2,400 lines)
| Module | Lines | Responsibility |
|---|---|---|
| `intelligence_backend.py` | 1,367 | Core CRM intelligence: audit_tasks, audit_contacts, pipeline analytics, duplicate detection, lifecycle alerts, tag/field auditing |
| `pipeline_b_data_bridge.py` | 258 | Data bridge: get_contacts, get_opportunities, get_tasks, get_appointments from data_store |

### Wrapper Stub Modules (6 files, ~46 lines total)
These are thin wrappers that re-export functions from `intelligence_backend.py` and load demo data from `pipeline_b_data_bridge.py`. They exist because server.py imports them by name.

| Module | Lines | Wraps |
|---|---|---|
| `crm_data_quality_auditor.py` | 7 | `intelligence_backend.crm_audit_all_contacts` + `DEMO_CONTACTS` |
| `duplicate_detector.py` | 7 | `intelligence_backend.crm_detect_duplicates` + `DEMO_CONTACTS` |
| `pipeline_analytics.py` | 7 | `intelligence_backend.crm_calculate_pipeline_analytics` + `DEMO_OPPORTUNITIES` |
| `contact_lifecycle_manager.py` | 7 | `intelligence_backend.crm_find_lifecycle_alerts` + `DEMO_CONTACTS` |
| `task_appointment_auditor.py` | 10 | `intelligence_backend.crm_audit_tasks/appointments` + `DEMO_TASKS/APPOINTMENTS` |
| `tag_field_manager.py` | 8 | `intelligence_backend.crm_audit_tags/fields` + `DEMO_GHL_TAGS/FIELDS` |

**V3 recommendation:** Inline these into server.py imports directly from `intelligence_backend.py`. Delete the 6 stub files.

### Action System (4 files, ~2,400 lines)
| Module | Lines | Responsibility |
|---|---|---|
| `action_ledger.py` | 739 | 7-state action state machine, CRUD, history, metrics, follow-ups |
| `action_store.py` | 484 | Action persistence layer (DB-backed) |
| `action_execution_engine.py` | 447 | Smart action buttons, AI message drafts, action cards, executability checks |
| `command_center_action_engine.py` | 326 | Generates prioritized recommendations → actions |

**V3 recommendation:** Consolidate `action_store.py` into `action_ledger.py` (both manage action persistence). Keep `action_execution_engine.py` separate (smart action UI logic).

### Revenue Modules (6 files, ~1,100 lines) — OVERLAP RISK
| Module | Lines | Responsibility |
|---|---|---|
| `revenue_data_adapter.py` | ~150 | Fetches revenue records from data_store |
| `revenue_opportunity_engine.py` | ~200 | Identifies revenue opportunities (upsell, cross-sell) |
| `revenue_opportunity_model.py` | ~150 | Models revenue opportunity scoring |
| `revenue_action_plan_engine.py` | ~150 | Generates action plans from revenue gaps |
| `revenue_risk_engine.py` | ~150 | Identifies revenue at risk (churn, downgrade) |
| `revenue_gap_analysis.py` | ~150 | Calculates gap between actual and target revenue |
| `revenue_category_engine.py` | ~100 | Breaks down revenue by category/source |
| `revenue_target_engine.py` | ~100 | Manages revenue targets/goals |

**V3 recommendation:** Consolidate into 2 files:
- `revenue_service.py` — data access, gap analysis, category breakdown, targets
- `revenue_intelligence.py` — opportunity detection, risk assessment, action plans

### Referral Modules (10 files, ~1,200 lines) — OVERLAP RISK
| Module | Lines | Responsibility |
|---|---|---|
| `referral_source_database.py` | ~100 | Manages referral source records |
| `referral_attribution_engine.py` | ~150 | Attributes revenue to referral sources |
| `referral_funnel_tracker.py` | ~100 | Tracks referral funnel (contact → lead → customer) |
| `referral_opportunity_engine.py` | ~150 | Identifies referral opportunities (who to ask) |
| `referral_gap_detector.py` | ~100 | Finds gaps in referral pipeline |
| `referral_potential_score.py` | ~100 | Scores referral potential of clients |
| `referral_timing_engine.py` | ~100 | Determines optimal timing for referral requests |
| `referral_value_analysis.py` | ~100 | Analyzes value of referral sources |
| `referral_leaderboard.py` | ~100 | Ranks referral sources by performance |
| `referral_campaign_engine.py` | ~150 | Manages referral campaigns |

**V3 recommendation:** Consolidate into 2 files:
- `referral_service.py` — source database, attribution, funnel tracking, leaderboard, value analysis
- `referral_intelligence.py` — opportunity detection, gap detection, potential scoring, timing, campaigns

### Client/CLV Modules (8 files, ~1,000 lines)
| Module | Lines | Responsibility |
|---|---|---|
| `client_value_matrix.py` | ~120 | Client value matrix (high/low value × high/low risk) |
| `client_value_segmentation.py` | ~120 | Segments clients by value tiers |
| `client_portfolio_analysis.py` | ~120 | Portfolio-level client analysis |
| `client_concentration_risk.py` | ~100 | Detects over-reliance on few clients |
| `client_risk_engine.py` | ~100 | Assesses individual client risk |
| `client_opportunity_engine.py` | ~100 | Identifies client growth opportunities |
| `clv_calculation_engine.py` | ~100 | Calculates CLV |
| `clv_score_engine.py` | ~100 | Scores clients by CLV |
| `clv_data_adapter.py` | ~100 | Fetches CLV-relevant data |
| `executive_clv_briefing.py` | ~100 | Summarizes CLV for executive view |

**V3 recommendation:** Consolidate into 2 files:
- `client_service.py` — portfolio, segmentation, concentration, risk, value matrix
- `clv_engine.py` — calculation, scoring, data adapter, executive briefing

### Lead Modules (2 files, ~250 lines)
| Module | Lines | Responsibility |
|---|---|---|
| `lead_scoring_engine.py` | ~150 | Scores leads by conversion probability |
| `lead_decay_engine.py` | ~100 | Detects decaying/stale leads |

**Status:** No overlap. Fine as-is.

### Daily Briefing Modules (3 files, ~600 lines)
| Module | Lines | Responsibility |
|---|---|---|
| `daily_priority_engine.py` | ~200 | Generates daily priority list |
| `daily_revenue_briefing.py` | ~200 | Daily revenue summary |
| `daily_referral_briefing.py` | ~200 | Daily referral opportunities |

**V3 recommendation:** Consolidate into `daily_briefing.py`.

### Business Scorecard (3 files, ~3,000 lines)
| Module | Lines | Responsibility |
|---|---|---|
| `business_scorecard_engine.py` | 1,461 | Core scorecard calculation (12 categories) |
| `business_scorecard_config.py` | 529 | Scorecard configuration (weights, thresholds) |
| `business_health_score.py` | ~100 | Overall health score + grade |
| `business_movement_score.py` | ~100 | Movement/trend score |

**V3 recommendation:** Merge `business_health_score.py` and `business_movement_score.py` into `business_scorecard_engine.py`. Keep config separate.

### Executive / Command Center (4 files, ~2,700 lines)
| Module | Lines | Responsibility |
|---|---|---|
| `command_center_v2_engine.py` | 1,008 | Main command center data aggregation |
| `owner_operating_layer.py` | 749 | Daily owner operating dashboard data |
| `command_center_action_engine.py` | 326 | Action generation for command center |
| `command_center_audit.py` | 705 | Audit logging for command center |

**Status:** Overlapping responsibilities but different use cases. Document for V3 review.

### Change Detection (5 files, ~600 lines)
| Module | Lines | Responsibility |
|---|---|---|
| `change_detection_engine.py` | ~150 | Detects changes between periods |
| `business_movement_score.py` | ~100 | Movement score (also in scorecard domain) |
| `exception_detection_engine.py` | ~100 | Detects exceptions/anomalies |
| `trend_analysis_engine.py` | ~100 | Analyzes trends over time |
| `missed_opportunity_detector.py` | ~100 | Finds missed opportunities |
| `what_changed_data_adapter.py` | ~100 | Fetches state for comparison |

**V3 recommendation:** Consolidate into `change_intelligence.py` (all work together in the "What Changed?" endpoint).

### Other Modules (single-purpose, no overlap)
| Module | Lines | Responsibility |
|---|---|---|
| `forecasting_model.py` | ~200 | Revenue forecasting |
| `scenario_forecasting_engine.py` | ~200 | Scenario-based forecasting |
| `product_forecast_engine.py` | ~100 | Product-level forecasting |
| `source_forecast_engine.py` | ~100 | Source-level forecasting |
| `future_prediction_engine.py` | ~100 | Future state predictions |
| `next_best_action_engine.py` | ~100 | Next best action recommendations |
| `who_should_i_call_engine.py` | ~100 | Call priority recommendations |
| `conversion_probability_model.py` | ~100 | Lead conversion probability |
| `relationship_health_score.py` | ~100 | Relationship health scoring |
| `marketing_posts_engine.py` | 312 | Marketing post generation |
| `training_mode_engine.py` | 1,192 | Training mode (15 modules, 5 simulations) |
| `feedback_engine.py` | 673 | User feedback system |
| `health_monitor.py` | 724 | System health monitoring |
| `import_engine.py` | 381 | Data import wizard |
| `demo_business_data.py` | 928 | Demo business sample data |
| `business_data_service.py` | 1,077 | Business data aggregation service |
| `business_data_adapter.py` | 242 | Data adapter for business contacts |
| `business_movement_score.py` | ~100 | Business movement/trend score |
| `executive_data_adapter.py` | ~150 | Executive data adapter |
| `revenue_data_adapter.py` | ~150 | Revenue data adapter |
| `ai_insights_generator.py` | ~100 | AI insights generation |
| `ai_activity_monitor.py` | ~100 | AI activity monitoring |
| `agent_coordination_monitor.py` | ~100 | Agent coordination monitoring |
| `cross_agent_sync_checker.py` | ~100 | Cross-agent sync verification |
| `escalation_engine.py` | ~100 | Escalation generation |
| `partner_intelligence_engine.py` | ~100 | Partner intelligence |
| `partner_opportunity_detector.py` | ~100 | Partner opportunity detection |

---

## V3 Refactoring Roadmap

### Phase 1: Safe deletions (this PR)
- [x] Delete 4 patch scripts
- [x] Move 5 diagnostic scripts to backend/scripts/
- [x] Remove dead safe_import + unused imports
- [x] Mark unused aliased imports with noqa comments

### Phase 2: Eliminate wrapper stubs (low risk)
- [ ] Inline 6 wrapper stub modules into server.py imports from intelligence_backend.py
- [ ] Delete the 6 stub files

### Phase 3: Consolidate revenue modules (medium risk)
- [ ] Merge into `revenue_service.py` (data access, gaps, categories, targets)
- [ ] Merge into `revenue_intelligence.py` (opportunities, risk, action plans)
- [ ] Update all imports in server.py

### Phase 4: Consolidate referral modules (medium risk)
- [ ] Merge into `referral_service.py` (sources, attribution, funnel, leaderboard)
- [ ] Merge into `referral_intelligence.py` (opportunities, gaps, timing, campaigns)

### Phase 5: Consolidate client/CLV modules (medium risk)
- [ ] Merge into `client_service.py` (portfolio, segmentation, concentration, risk)
- [ ] Merge into `clv_engine.py` (calculation, scoring, briefing)

### Phase 6: Split server.py monolith (high risk, high reward)
- [ ] Extract route modules: `routes/summary.py`, `routes/actions.py`, `routes/calendar.py`, `routes/communications.py`, `routes/training.py`, `routes/admin.py`
- [ ] Keep `server.py` as app setup + route registration only
