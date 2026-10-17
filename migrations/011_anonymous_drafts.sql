-- Draft-only research before signup: one page fetch and one model call, never a search. Nothing here belongs to a
-- workspace. The API role has no privileges on these tables; it can only create, read and take a draft through the
-- functions below, each scoped by the SHA-256 of a claim token held by one browser. The worker drafts queued rows.
CREATE TABLE shortlist.anonymous_drafts (
    id UUID PRIMARY KEY,
    claim_hash TEXT NOT NULL CHECK (claim_hash ~ '^[0-9a-f]{64}$'),
    website TEXT NOT NULL CHECK (length(website) <= 2048),
    status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','running','ready','failed')),
    source TEXT, draft TEXT, error TEXT,
    events TEXT NOT NULL DEFAULT '[]',
    lease_until DOUBLE PRECISION NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL DEFAULT now() + interval '24 hours'
);
CREATE INDEX anonymous_drafts_pending ON shortlist.anonymous_drafts(status, created_at);
-- One draft per browser and per network address each day. Only keyed hashes are kept, never addresses.
CREATE TABLE shortlist.anonymous_visitors (
    visitor_hash TEXT NOT NULL CHECK (visitor_hash ~ '^[0-9a-f]{64}$'),
    day DATE NOT NULL,
    PRIMARY KEY (visitor_hash, day)
);
-- A ceiling on anonymous model calls across all visitors each day.
CREATE TABLE shortlist.anonymous_usage (day DATE PRIMARY KEY, drafts INTEGER NOT NULL CHECK (drafts >= 1));

CREATE FUNCTION shortlist.create_anonymous_draft(draft_id UUID, claim TEXT, page TEXT, visitors TEXT[], daily_cap INTEGER)
RETURNS TEXT LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE added INTEGER; counted INTEGER;
BEGIN
    IF daily_cap NOT BETWEEN 1 AND 1000 THEN RAISE EXCEPTION 'Invalid anonymous draft cap'; END IF;
    IF cardinality(visitors) NOT BETWEEN 1 AND 4 THEN RAISE EXCEPTION 'Invalid visitor keys'; END IF;
    DELETE FROM shortlist.anonymous_drafts WHERE expires_at < now();
    DELETE FROM shortlist.anonymous_visitors WHERE day < CURRENT_DATE - 1;
    DELETE FROM shortlist.anonymous_usage WHERE day < CURRENT_DATE - 7;
    BEGIN
        -- A limit inside this block rolls back its partial inserts, so a refused visitor marks nothing.
        INSERT INTO shortlist.anonymous_visitors(visitor_hash, day)
            SELECT DISTINCT key, CURRENT_DATE FROM unnest(visitors) AS key ON CONFLICT DO NOTHING;
        GET DIAGNOSTICS added = ROW_COUNT;
        IF added < (SELECT count(DISTINCT key) FROM unnest(visitors) AS key) THEN
            RAISE EXCEPTION 'visitor_limit';
        END IF;
        INSERT INTO shortlist.anonymous_usage(day, drafts) VALUES (CURRENT_DATE, 1)
        ON CONFLICT (day) DO UPDATE SET drafts = shortlist.anonymous_usage.drafts + 1
            WHERE shortlist.anonymous_usage.drafts < daily_cap RETURNING drafts INTO counted;
        IF counted IS NULL THEN RAISE EXCEPTION 'daily_limit'; END IF;
        INSERT INTO shortlist.anonymous_drafts(id, claim_hash, website) VALUES (draft_id, claim, page);
    EXCEPTION WHEN raise_exception THEN
        RETURN SQLERRM;
    END;
    RETURN 'created';
END $$;

CREATE FUNCTION shortlist.read_anonymous_draft(draft_id UUID, claim TEXT)
RETURNS TABLE(status TEXT, website TEXT, draft TEXT, error TEXT, events TEXT)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path='' AS $$
    SELECT d.status, d.website, d.draft, d.error, d.events FROM shortlist.anonymous_drafts d
    WHERE d.id = draft_id AND d.claim_hash = claim AND d.expires_at > now()
$$;

-- Removes the draft as it becomes a run; the caller creates that run in the same transaction.
CREATE FUNCTION shortlist.take_anonymous_draft(draft_id UUID, claim TEXT)
RETURNS TABLE(status TEXT, website TEXT, source TEXT, draft TEXT)
LANGUAGE sql SECURITY DEFINER SET search_path='' AS $$
    DELETE FROM shortlist.anonymous_drafts d
    WHERE d.id = draft_id AND d.claim_hash = claim AND d.expires_at > now() AND d.status IN ('ready','failed')
    RETURNING d.status, d.website, d.source, d.draft
$$;

REVOKE ALL ON FUNCTION shortlist.create_anonymous_draft(UUID,TEXT,TEXT,TEXT[],INTEGER) FROM PUBLIC;
REVOKE ALL ON FUNCTION shortlist.read_anonymous_draft(UUID,TEXT) FROM PUBLIC;
REVOKE ALL ON FUNCTION shortlist.take_anonymous_draft(UUID,TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION shortlist.create_anonymous_draft(UUID,TEXT,TEXT,TEXT[],INTEGER) TO shortlist_api;
GRANT EXECUTE ON FUNCTION shortlist.read_anonymous_draft(UUID,TEXT) TO shortlist_api;
GRANT EXECUTE ON FUNCTION shortlist.take_anonymous_draft(UUID,TEXT) TO shortlist_api;
GRANT SELECT, UPDATE ON shortlist.anonymous_drafts TO shortlist_worker;
