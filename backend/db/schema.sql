-- Auto-Ecommerce ClickHouse schema
-- One file, idempotent (uses CREATE TABLE IF NOT EXISTS).
-- All timestamps default to now() so writers can omit them.

CREATE TABLE IF NOT EXISTS businesses (
    id UUID,
    product_name String,
    slug String,
    category String,
    launch_time DateTime DEFAULT now(),
    store_url String,
    status Enum8('active' = 1, 'failed' = 2, 'paused' = 3),
    margin_estimate Float32,
    supplier_id String,
    supplier_name String,
    trend_score Float32,
    launch_score Float32,
    bias_score Float32 DEFAULT 0,
    created_at DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (category, launch_time, id);

CREATE TABLE IF NOT EXISTS trend_signals (
    id UUID,
    product_name String,
    category String,
    source LowCardinality(String),
    trend_score Float32,
    search_volume UInt32,
    social_mentions UInt32,
    detected_at DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (detected_at, id);

CREATE TABLE IF NOT EXISTS agent_decisions (
    id UUID,
    business_id UUID,
    run_id UUID,
    agent_name LowCardinality(String),
    action String,
    input_summary String,
    output_summary String,
    latency_ms UInt32,
    model_used LowCardinality(String),
    timestamp DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (agent_name, timestamp);

CREATE TABLE IF NOT EXISTS launch_runs (
    run_id UUID,
    temporal_workflow_id String,
    product_name String,
    slug String,
    status Enum8(
        'started' = 1,
        'running' = 2,
        'completed' = 3,
        'failed' = 4,
        'fallback_completed' = 5
    ),
    launch_score Float32 DEFAULT 0,
    decision LowCardinality(String) DEFAULT '',
    store_url String DEFAULT '',
    started_at DateTime DEFAULT now(),
    completed_at Nullable(DateTime),
    error Nullable(String)
) ENGINE = MergeTree()
ORDER BY (started_at, run_id);

CREATE TABLE IF NOT EXISTS agent_events (
    run_id UUID,
    business_id Nullable(UUID),
    agent_name LowCardinality(String),
    event_type Enum8(
        'pending' = 1,
        'running' = 2,
        'completed' = 3,
        'failed' = 4,
        'fallback_used' = 5
    ),
    message String,
    payload String,
    timestamp DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (run_id, timestamp);

CREATE TABLE IF NOT EXISTS business_relationships (
    from_business_id UUID,
    to_business_id UUID,
    relationship_type LowCardinality(String),
    weight Float32,
    reason String,
    created_at DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (from_business_id, relationship_type);

CREATE TABLE IF NOT EXISTS users (
    id UUID,
    email String,
    password_hash String,
    full_name String DEFAULT '',
    is_active UInt8 DEFAULT 1,
    created_at DateTime DEFAULT now(),
    last_login_at Nullable(DateTime)
) ENGINE = MergeTree()
ORDER BY (email, created_at, id);
