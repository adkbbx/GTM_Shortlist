ALTER TABLE shortlist.records ADD CONSTRAINT records_run_owner UNIQUE(id,run_id,workspace_id);
CREATE TABLE shortlist.operator_reviews (
    id TEXT PRIMARY KEY,
    workspace_id UUID NOT NULL DEFAULT nullif(current_setting('shortlist.workspace_id',true),'')::uuid,
    position BIGINT GENERATED ALWAYS AS IDENTITY,
    run_id TEXT NOT NULL,
    record_id TEXT NOT NULL,
    request_key TEXT NOT NULL,
    command_hash TEXT NOT NULL,
    payload TEXT NOT NULL,
    UNIQUE(run_id,record_id,request_key),
    FOREIGN KEY(record_id,run_id,workspace_id) REFERENCES shortlist.records(id,run_id,workspace_id) ON DELETE CASCADE
);
CREATE INDEX operator_review_history ON shortlist.operator_reviews(record_id,position);
ALTER TABLE shortlist.operator_reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE shortlist.operator_reviews FORCE ROW LEVEL SECURITY;
CREATE POLICY operator_review_scope ON shortlist.operator_reviews
    USING (workspace_id=nullif(current_setting('shortlist.workspace_id',true),'')::uuid)
    WITH CHECK (current_user='shortlist_worker'
        AND workspace_id=nullif(current_setting('shortlist.workspace_id',true),'')::uuid);
GRANT SELECT ON shortlist.operator_reviews TO shortlist_api;
GRANT SELECT,INSERT ON shortlist.operator_reviews TO shortlist_worker;
GRANT USAGE,SELECT ON SEQUENCE shortlist.operator_reviews_position_seq TO shortlist_worker;
