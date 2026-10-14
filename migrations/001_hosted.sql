-- Apply only with migration/operator credentials. Never expose this schema to PostgREST.
CREATE SCHEMA IF NOT EXISTS shortlist;
REVOKE ALL ON SCHEMA shortlist FROM PUBLIC;

DO $$ BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='shortlist_api') THEN
        CREATE ROLE shortlist_api NOLOGIN NOSUPERUSER NOBYPASSRLS;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='shortlist_worker') THEN
        CREATE ROLE shortlist_worker NOLOGIN NOSUPERUSER NOBYPASSRLS;
    END IF;
END $$;

CREATE TABLE shortlist.workspaces (
    id UUID PRIMARY KEY DEFAULT nullif(current_setting('shortlist.workspace_id',true),'')::uuid,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(id)
);
CREATE TABLE shortlist.runs (
    id TEXT PRIMARY KEY,
    workspace_id UUID NOT NULL DEFAULT nullif(current_setting('shortlist.workspace_id',true),'')::uuid
        REFERENCES shortlist.workspaces(id) ON DELETE CASCADE,
    position BIGINT GENERATED ALWAYS AS IDENTITY,
    request_key TEXT NOT NULL, payload_hash TEXT NOT NULL, profile TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('queued','running','awaiting_confirmation','ready','partial')),
    stage TEXT NOT NULL, checkpoint TEXT NOT NULL DEFAULT '{}', error TEXT,
    lease_until DOUBLE PRECISION NOT NULL DEFAULT 0, fence INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
    UNIQUE(workspace_id,request_key), UNIQUE(id,workspace_id)
);
CREATE TABLE shortlist.records (
    id TEXT PRIMARY KEY,
    workspace_id UUID NOT NULL DEFAULT nullif(current_setting('shortlist.workspace_id',true),'')::uuid,
    position BIGINT GENERATED ALWAYS AS IDENTITY,
    run_id TEXT NOT NULL, domain TEXT NOT NULL, research TEXT NOT NULL, review TEXT,
    UNIQUE(run_id,domain), FOREIGN KEY(run_id,workspace_id) REFERENCES shortlist.runs(id,workspace_id) ON DELETE CASCADE
);
CREATE TABLE shortlist.attempts (
    id TEXT PRIMARY KEY,
    workspace_id UUID NOT NULL DEFAULT nullif(current_setting('shortlist.workspace_id',true),'')::uuid,
    position BIGINT GENERATED ALWAYS AS IDENTITY,
    run_id TEXT NOT NULL, provider TEXT NOT NULL, kind TEXT NOT NULL CHECK(kind IN ('search','model','fetch')),
    month TEXT NOT NULL, operation_key TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('outcome_unknown','succeeded','failed')), created_at TEXT NOT NULL,
    UNIQUE(run_id,operation_key), UNIQUE(id,workspace_id),
    FOREIGN KEY(run_id,workspace_id) REFERENCES shortlist.runs(id,workspace_id) ON DELETE CASCADE
);
CREATE TABLE shortlist.attempt_results (
    attempt_id TEXT PRIMARY KEY,
    workspace_id UUID NOT NULL DEFAULT nullif(current_setting('shortlist.workspace_id',true),'')::uuid,
    request_hash TEXT NOT NULL, payload TEXT,
    FOREIGN KEY(attempt_id,workspace_id) REFERENCES shortlist.attempts(id,workspace_id) ON DELETE CASCADE
);
CREATE TABLE shortlist.source_cache (
    source_id TEXT PRIMARY KEY,
    workspace_id UUID NOT NULL DEFAULT nullif(current_setting('shortlist.workspace_id',true),'')::uuid
        REFERENCES shortlist.workspaces(id) ON DELETE CASCADE,
    position BIGINT GENERATED ALWAYS AS IDENTITY,
    requested_url TEXT NOT NULL, domain TEXT NOT NULL, retrieved_epoch DOUBLE PRECISION NOT NULL, payload TEXT NOT NULL
);
CREATE INDEX source_cache_lookup ON shortlist.source_cache(workspace_id,requested_url,domain,retrieved_epoch);
CREATE INDEX pending_runs ON shortlist.runs(status,lease_until,created_at,position);
CREATE TABLE shortlist.run_events (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    workspace_id UUID NOT NULL DEFAULT nullif(current_setting('shortlist.workspace_id',true),'')::uuid,
    run_id TEXT NOT NULL, phase TEXT NOT NULL, label TEXT NOT NULL, state TEXT NOT NULL,
    detail TEXT, created_at TEXT NOT NULL,
    FOREIGN KEY(run_id,workspace_id) REFERENCES shortlist.runs(id,workspace_id) ON DELETE CASCADE
);
CREATE TABLE shortlist.worker_heartbeats(id TEXT PRIMARY KEY,expires_at DOUBLE PRECISION NOT NULL);

-- Each policy has both read and write checks. Runtime roles never own tables.
DO $$ DECLARE table_name TEXT; BEGIN
    FOREACH table_name IN ARRAY ARRAY['runs','records','attempts','attempt_results','source_cache','run_events'] LOOP
        EXECUTE format('ALTER TABLE shortlist.%I ENABLE ROW LEVEL SECURITY',table_name);
        EXECUTE format('ALTER TABLE shortlist.%I FORCE ROW LEVEL SECURITY',table_name);
        EXECUTE format('CREATE POLICY workspace_scope ON shortlist.%I USING '
            '(current_user=''shortlist_worker'' OR workspace_id=nullif(current_setting(''shortlist.workspace_id'',true),'''')::uuid) '
            'WITH CHECK (current_user=''shortlist_worker'' OR workspace_id=nullif(current_setting(''shortlist.workspace_id'',true),'''')::uuid)',table_name);
    END LOOP;
END $$;
ALTER TABLE shortlist.workspaces ENABLE ROW LEVEL SECURITY;
ALTER TABLE shortlist.workspaces FORCE ROW LEVEL SECURITY;
CREATE POLICY owner_workspace ON shortlist.workspaces
    USING(current_user='shortlist_worker' OR id=nullif(current_setting('shortlist.workspace_id',true),'')::uuid)
    WITH CHECK(current_user='shortlist_worker' OR id=nullif(current_setting('shortlist.workspace_id',true),'')::uuid);

-- Aggregate allowance is shared across workspaces; private rows remain unreadable.
CREATE TABLE shortlist.search_quotas(provider TEXT NOT NULL,month TEXT NOT NULL,used INTEGER NOT NULL,
    PRIMARY KEY(provider,month),CHECK(used BETWEEN 1 AND 250));
CREATE FUNCTION shortlist.reserve_search_quota(provider_key TEXT,month_key TEXT,attempt_cap INTEGER)
RETURNS BOOLEAN LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE reserved INTEGER;
BEGIN
    IF attempt_cap NOT BETWEEN 1 AND 250 THEN RAISE EXCEPTION 'Invalid global search cap'; END IF;
    INSERT INTO shortlist.search_quotas(provider,month,used) VALUES(provider_key,month_key,1)
    ON CONFLICT(provider,month) DO UPDATE SET used=shortlist.search_quotas.used+1
        WHERE shortlist.search_quotas.used<attempt_cap RETURNING used INTO reserved;
    RETURN reserved IS NOT NULL;
END $$;
REVOKE ALL ON FUNCTION shortlist.reserve_search_quota(TEXT,TEXT,INTEGER) FROM PUBLIC;
GRANT USAGE ON SCHEMA shortlist TO shortlist_api,shortlist_worker;
GRANT SELECT,INSERT,UPDATE,DELETE ON shortlist.workspaces,shortlist.runs,shortlist.records,
    shortlist.attempts,shortlist.attempt_results,shortlist.source_cache,shortlist.run_events TO shortlist_api,shortlist_worker;
GRANT SELECT ON shortlist.worker_heartbeats TO shortlist_api;
GRANT SELECT,INSERT,UPDATE,DELETE ON shortlist.worker_heartbeats TO shortlist_worker;
GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA shortlist TO shortlist_api,shortlist_worker;
GRANT EXECUTE ON FUNCTION shortlist.reserve_search_quota(TEXT,TEXT,INTEGER) TO shortlist_api,shortlist_worker;
