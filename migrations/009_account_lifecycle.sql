ALTER TABLE shortlist.workspaces
    ADD COLUMN closure_state TEXT NOT NULL DEFAULT 'open' CHECK(closure_state IN ('open','closing','closed')),
    ADD COLUMN closure_requested_at TIMESTAMPTZ,
    ADD COLUMN closure_completed_at TIMESTAMPTZ;
ALTER TABLE shortlist.workspaces ADD CONSTRAINT workspace_closure_dates CHECK (
    (closure_state='open' AND closure_requested_at IS NULL AND closure_completed_at IS NULL)
    OR (closure_state='closing' AND closure_requested_at IS NOT NULL AND closure_completed_at IS NULL)
    OR (closure_state='closed' AND closure_requested_at IS NOT NULL AND closure_completed_at IS NOT NULL)
);

CREATE FUNCTION shortlist.monotonic_account_closure() RETURNS trigger
LANGUAGE plpgsql SET search_path='' AS $$
BEGIN
    IF NOT (NEW.closure_state=OLD.closure_state
        OR (OLD.closure_state='open' AND NEW.closure_state='closing')
        OR (OLD.closure_state='closing' AND NEW.closure_state='closed')) THEN
        RAISE EXCEPTION 'Closed accounts cannot reopen' USING ERRCODE='42501';
    END IF;
    RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION shortlist.monotonic_account_closure() FROM PUBLIC;
CREATE TRIGGER monotonic_account_closure BEFORE UPDATE ON shortlist.workspaces
    FOR EACH ROW EXECUTE FUNCTION shortlist.monotonic_account_closure();

CREATE FUNCTION shortlist.require_open_research_account() RETURNS trigger
LANGUAGE plpgsql SET search_path='' AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM shortlist.workspaces WHERE id=NEW.workspace_id AND closure_state='open') THEN
        RAISE EXCEPTION 'This research account is unavailable' USING ERRCODE='42501';
    END IF;
    RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION shortlist.require_open_research_account() FROM PUBLIC;
CREATE TRIGGER require_open_research_account BEFORE INSERT ON shortlist.runs
    FOR EACH ROW EXECUTE FUNCTION shortlist.require_open_research_account();
