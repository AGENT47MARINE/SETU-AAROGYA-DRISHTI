-- Init extensions
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Districts with spatial data
CREATE TABLE IF NOT EXISTS districts (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    state       VARCHAR(100) NOT NULL,
    population  INTEGER,
    geom        GEOMETRY(MULTIPOLYGON, 4326)
);
CREATE INDEX IF NOT EXISTS districts_geom_idx ON districts USING GIST (geom);
CREATE UNIQUE INDEX IF NOT EXISTS districts_name_state_uniq_idx
ON districts (LOWER(name), LOWER(state));

-- Core post table (hypertable partitioned by day)
CREATE TABLE IF NOT EXISTS posts (
    id              UUID DEFAULT gen_random_uuid(),
    platform        VARCHAR(50) NOT NULL,
    post_id_hash    VARCHAR(64) NOT NULL,
    text_cleaned    TEXT NOT NULL,
    text_translated TEXT,
    detected_lang   VARCHAR(10),
    district_mapping_method VARCHAR(50),
    district_id     INTEGER REFERENCES districts(id),
    geom            GEOMETRY(POINT, 4326),
    posted_at       TIMESTAMPTZ NOT NULL,
    ingested_at     TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (id, posted_at)
);
CREATE UNIQUE INDEX IF NOT EXISTS posts_platform_hash_time_uniq_idx
ON posts (platform, post_id_hash, posted_at);

-- Convert to hypertable if not already
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM _timescaledb_catalog.hypertable WHERE table_name = 'posts') THEN
        PERFORM create_hypertable('posts', 'posted_at', chunk_time_interval => INTERVAL '1 day');
    END IF;
END $$;

-- Medical entities extracted from posts
CREATE TABLE IF NOT EXISTS post_entities (
    id              UUID DEFAULT gen_random_uuid(),
    post_id         UUID,
    posted_at       TIMESTAMPTZ NOT NULL,
    entity_type     VARCHAR(20) NOT NULL,
    entity_text     TEXT NOT NULL,
    ontology_code   VARCHAR(50),
    ontology_system VARCHAR(20),
    confidence      FLOAT,
    PRIMARY KEY (id, posted_at)
);

-- Convert to hypertable if not already
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM _timescaledb_catalog.hypertable WHERE table_name = 'post_entities') THEN
        PERFORM create_hypertable('post_entities', 'posted_at', chunk_time_interval => INTERVAL '1 day');
    END IF;
END $$;

-- Aggregated signal counts
CREATE TABLE IF NOT EXISTS signal_counts (
    district_id     INTEGER REFERENCES districts(id),
    entity_code     VARCHAR(50),
    entity_type     VARCHAR(20),
    window_start    TIMESTAMPTZ NOT NULL,
    window_end      TIMESTAMPTZ NOT NULL,
    count           INTEGER DEFAULT 0,
    PRIMARY KEY (district_id, entity_code, window_start)
);

-- Triage alerts
CREATE TABLE IF NOT EXISTS alerts (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    alert_type      VARCHAR(50) NOT NULL,
    severity        VARCHAR(20) NOT NULL,
    status          VARCHAR(30) DEFAULT 'PENDING_REVIEW',
    payload         JSONB NOT NULL,
    confidence      FLOAT,
    assigned_to     VARCHAR(100),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    reviewed_at     TIMESTAMPTZ,
    decision        VARCHAR(30),
    decision_notes  TEXT
);

-- Immutable audit log
CREATE TABLE IF NOT EXISTS audit_log (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    alert_id        UUID REFERENCES alerts(id),
    actor           VARCHAR(100),
    action          VARCHAR(50),
    payload_hash    VARCHAR(64),
    blockchain_txid VARCHAR(200),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
