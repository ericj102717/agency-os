-- Supabase / PostgreSQL schema migration
-- Translated from SQLite schema to PostgreSQL syntax
-- All tables use CREATE TABLE IF NOT EXISTS
-- All indexes use CREATE INDEX IF NOT EXISTS

-- 1. contacts
CREATE TABLE IF NOT EXISTS contacts (
    id SERIAL PRIMARY KEY,
    contact_id TEXT UNIQUE,
    first_name TEXT NOT NULL,
    last_name TEXT DEFAULT '',
    email TEXT DEFAULT '',
    normalized_email TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    normalized_phone TEXT DEFAULT '',
    date_of_birth TEXT,
    contact_type TEXT NOT NULL DEFAULT 'lead',
    lead_source TEXT DEFAULT '',
    pipeline_stage TEXT DEFAULT 'new',
    medicare_status TEXT DEFAULT '',
    email_consent INTEGER DEFAULT 0,
    sms_consent INTEGER DEFAULT 0,
    call_consent INTEGER DEFAULT 0,
    last_activity TEXT,
    client_since TEXT,
    zip_code TEXT DEFAULT '',
    state TEXT DEFAULT '',
    tags TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    is_sample INTEGER DEFAULT 0,
    import_batch_id TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 2. opportunities
CREATE TABLE IF NOT EXISTS opportunities (
    id SERIAL PRIMARY KEY,
    opp_id TEXT UNIQUE,
    contact_id TEXT,
    product_type TEXT DEFAULT '',
    stage TEXT NOT NULL DEFAULT 'new',
    entered_stage TEXT,
    expected_close TEXT,
    estimated_value REAL DEFAULT 0,
    created_date TEXT,
    stage_history TEXT DEFAULT '[]',
    is_sample INTEGER DEFAULT 0,
    import_batch_id TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 3. revenue_records
CREATE TABLE IF NOT EXISTS revenue_records (
    id SERIAL PRIMARY KEY,
    record_id TEXT UNIQUE,
    contact_id TEXT,
    product_type TEXT DEFAULT '',
    amount REAL NOT NULL DEFAULT 0,
    revenue_date TEXT,
    revenue_category TEXT DEFAULT 'commission',
    payment_status TEXT DEFAULT 'received',
    source TEXT DEFAULT '',
    is_sample INTEGER DEFAULT 0,
    import_batch_id TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 4. referral_sources
CREATE TABLE IF NOT EXISTS referral_sources (
    id SERIAL PRIMARY KEY,
    source_id TEXT UNIQUE,
    source_name TEXT NOT NULL,
    source_type TEXT DEFAULT 'client',
    contact_info TEXT DEFAULT '',
    relationship_strength INTEGER DEFAULT 50,
    referrals_generated INTEGER DEFAULT 0,
    referrals_converted INTEGER DEFAULT 0,
    conversion_rate REAL DEFAULT 0,
    total_revenue_generated REAL DEFAULT 0,
    last_referral_date TEXT,
    status TEXT DEFAULT 'active',
    is_sample INTEGER DEFAULT 0,
    import_batch_id TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 5. import_batches
CREATE TABLE IF NOT EXISTS import_batches (
    batch_id TEXT PRIMARY KEY,
    data_type TEXT NOT NULL,
    filename TEXT,
    total_rows INTEGER DEFAULT 0,
    valid_rows INTEGER DEFAULT 0,
    invalid_rows INTEGER DEFAULT 0,
    duplicate_rows INTEGER DEFAULT 0,
    imported_rows INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',
    field_mapping TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);

-- 6. import_issues
CREATE TABLE IF NOT EXISTS import_issues (
    id SERIAL PRIMARY KEY,
    batch_id TEXT,
    row_number INTEGER,
    field_name TEXT,
    issue_type TEXT,
    message TEXT,
    row_data TEXT
);

-- 7. business_config
CREATE TABLE IF NOT EXISTS business_config (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    business_name TEXT DEFAULT '',
    industry TEXT DEFAULT '',
    primary_objective TEXT DEFAULT '',
    revenue_goal REAL DEFAULT 0,
    goal_period TEXT DEFAULT 'monthly',
    avg_transaction_value REAL DEFAULT 0,
    current_revenue REAL DEFAULT 0,
    reporting_period TEXT DEFAULT 'monthly',
    setup_complete INTEGER DEFAULT 0,
    setup_completed_at TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 8. services
CREATE TABLE IF NOT EXISTS services (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    avg_price REAL DEFAULT 0,
    category TEXT DEFAULT '',
    is_active INTEGER DEFAULT 1,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 9. lead_sources
CREATE TABLE IF NOT EXISTS lead_sources (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT DEFAULT '',
    is_active INTEGER DEFAULT 1,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 10. sales_stages
CREATE TABLE IF NOT EXISTS sales_stages (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    label TEXT DEFAULT '',
    probability REAL DEFAULT 0,
    sort_order INTEGER DEFAULT 0,
    is_closed INTEGER DEFAULT 0,
    is_won INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 11. actions
CREATE TABLE IF NOT EXISTS actions (
    id SERIAL PRIMARY KEY,
    action_id TEXT UNIQUE,
    entity_type TEXT DEFAULT '',
    entity_id TEXT DEFAULT '',
    entity_name TEXT DEFAULT '',
    action_type TEXT NOT NULL,
    title TEXT DEFAULT '',
    description TEXT DEFAULT '',
    priority INTEGER DEFAULT 5,
    due_date TEXT,
    status TEXT DEFAULT 'pending',
    completed_date TEXT,
    expected_value REAL DEFAULT 0,
    actual_outcome TEXT DEFAULT '',
    recommendation_id TEXT,
    source_module TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 12. recommendations
CREATE TABLE IF NOT EXISTS recommendations (
    id SERIAL PRIMARY KEY,
    rec_id TEXT UNIQUE,
    entity_type TEXT DEFAULT '',
    entity_id TEXT DEFAULT '',
    rec_type TEXT NOT NULL,
    title TEXT DEFAULT '',
    description TEXT DEFAULT '',
    priority INTEGER DEFAULT 5,
    expected_impact TEXT DEFAULT '',
    ignore_consequence TEXT DEFAULT '',
    next_step TEXT DEFAULT '',
    explanation_data TEXT DEFAULT '{}',
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TEXT
);

-- 13. recommendation_feedback
CREATE TABLE IF NOT EXISTS recommendation_feedback (
    id SERIAL PRIMARY KEY,
    rec_id TEXT NOT NULL,
    user_action TEXT DEFAULT '',
    completed INTEGER DEFAULT 0,
    outcome TEXT DEFAULT '',
    revenue_generated REAL DEFAULT 0,
    conversion_result TEXT DEFAULT '',
    time_to_complete_hours REAL DEFAULT 0,
    feedback_notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT NOW()
);

-- 14. business_memory
CREATE TABLE IF NOT EXISTS business_memory (
    id SERIAL PRIMARY KEY,
    memory_id TEXT UNIQUE,
    entity_type TEXT DEFAULT '',
    entity_id TEXT DEFAULT '',
    entity_name TEXT DEFAULT '',
    memory_text TEXT NOT NULL,
    memory_category TEXT DEFAULT 'general',
    relevance_score INTEGER DEFAULT 50,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 15. user_preferences
CREATE TABLE IF NOT EXISTS user_preferences (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    revenue_goal REAL DEFAULT 85000,
    demo_mode INTEGER DEFAULT 1,
    auto_refresh INTEGER DEFAULT 1,
    refresh_interval INTEGER DEFAULT 60,
    notif_new_leads INTEGER DEFAULT 1,
    notif_revenue_gap INTEGER DEFAULT 1,
    notif_stuck_opps INTEGER DEFAULT 1,
    notif_referral_ops INTEGER DEFAULT 1,
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 16. demo_state
CREATE TABLE IF NOT EXISTS demo_state (
    business_id TEXT,
    scenario_id TEXT,
    state_json TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_contacts_email ON contacts(normalized_email);
CREATE INDEX IF NOT EXISTS idx_contacts_phone ON contacts(normalized_phone);
CREATE INDEX IF NOT EXISTS idx_contacts_type ON contacts(contact_type);
CREATE INDEX IF NOT EXISTS idx_opp_contact ON opportunities(contact_id);
CREATE INDEX IF NOT EXISTS idx_rev_contact ON revenue_records(contact_id);
CREATE INDEX IF NOT EXISTS idx_issues_batch ON import_issues(batch_id);
CREATE INDEX IF NOT EXISTS idx_actions_status ON actions(status);
CREATE INDEX IF NOT EXISTS idx_actions_entity ON actions(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_actions_priority ON actions(priority);
CREATE INDEX IF NOT EXISTS idx_recs_status ON recommendations(status);
CREATE INDEX IF NOT EXISTS idx_recs_entity ON recommendations(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_feedback_rec ON recommendation_feedback(rec_id);
CREATE INDEX IF NOT EXISTS idx_memory_entity ON business_memory(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_services_active ON services(is_active);
CREATE INDEX IF NOT EXISTS idx_lead_sources_active ON lead_sources(is_active);
CREATE INDEX IF NOT EXISTS idx_sales_stages_order ON sales_stages(sort_order);
