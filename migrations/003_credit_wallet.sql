CREATE TABLE shortlist.credit_entries (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    workspace_id UUID NOT NULL REFERENCES shortlist.workspaces(id),
    operation_key TEXT NOT NULL,
    kind TEXT NOT NULL CHECK(kind IN ('signup','purchase','usage','refund')),
    amount INTEGER NOT NULL,
    description TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(workspace_id,operation_key),
    CHECK((kind='signup' AND amount IN (0,3)) OR (kind IN ('purchase','refund') AND amount>0)
          OR (kind='usage' AND amount=-1))
);
CREATE TABLE shortlist.credit_reservations (
    run_id TEXT PRIMARY KEY,
    workspace_id UUID NOT NULL,
    requested INTEGER NOT NULL CHECK(requested BETWEEN 1 AND 3),
    consumed INTEGER NOT NULL DEFAULT 0,
    state TEXT NOT NULL DEFAULT 'held' CHECK(state IN ('held','settled','released')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK(consumed BETWEEN 0 AND requested),
    FOREIGN KEY(run_id,workspace_id) REFERENCES shortlist.runs(id,workspace_id)
);
DO $$ DECLARE table_name TEXT; BEGIN
    FOREACH table_name IN ARRAY ARRAY['credit_entries','credit_reservations'] LOOP
        EXECUTE format('ALTER TABLE shortlist.%I ENABLE ROW LEVEL SECURITY',table_name);
        EXECUTE format('ALTER TABLE shortlist.%I FORCE ROW LEVEL SECURITY',table_name);
        EXECUTE format('CREATE POLICY credit_workspace ON shortlist.%I USING '
            '(current_user=''shortlist_worker'' OR workspace_id=nullif(current_setting(''shortlist.workspace_id'',true),'''')::uuid) '
            'WITH CHECK (current_user=''shortlist_worker'' OR workspace_id=nullif(current_setting(''shortlist.workspace_id'',true),'''')::uuid)',table_name);
    END LOOP;
END $$;
CREATE INDEX credit_entries_workspace ON shortlist.credit_entries(workspace_id,created_at,id);
CREATE INDEX credit_reservations_workspace ON shortlist.credit_reservations(workspace_id,state);
GRANT SELECT ON shortlist.credit_entries TO shortlist_api;
GRANT SELECT,INSERT ON shortlist.credit_entries TO shortlist_worker;
GRANT SELECT,INSERT,UPDATE ON shortlist.credit_reservations TO shortlist_api,shortlist_worker;

-- Existing used demos never receive a second free allowance. Preserve a zero
-- entry for that once-only decision rather than pretending they were charged.
INSERT INTO shortlist.credit_entries(workspace_id,operation_key,kind,amount,description)
SELECT id,'signup','signup',CASE WHEN demo_run_id IS NULL THEN 3 ELSE 0 END,
    CASE WHEN demo_run_id IS NULL THEN 'Signup research credits' ELSE 'Legacy demo already granted' END
FROM shortlist.workspaces;

CREATE FUNCTION shortlist.signup_credit_grant() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
BEGIN
    INSERT INTO shortlist.credit_entries(workspace_id,operation_key,kind,amount,description)
        VALUES(NEW.id,'signup','signup',3,'Signup research credits');
    RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION shortlist.signup_credit_grant() FROM PUBLIC;
CREATE TRIGGER signup_credit_grant AFTER INSERT ON shortlist.workspaces
    FOR EACH ROW EXECUTE FUNCTION shortlist.signup_credit_grant();
