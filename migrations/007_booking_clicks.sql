CREATE TABLE shortlist.booking_clicks (
    id TEXT PRIMARY KEY,
    workspace_id UUID NOT NULL DEFAULT nullif(current_setting('shortlist.workspace_id',true),'')::uuid,
    run_id TEXT NOT NULL,
    request_key TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(run_id,request_key),
    FOREIGN KEY(run_id,workspace_id) REFERENCES shortlist.runs(id,workspace_id) ON DELETE CASCADE
);
ALTER TABLE shortlist.booking_clicks ENABLE ROW LEVEL SECURITY;
ALTER TABLE shortlist.booking_clicks FORCE ROW LEVEL SECURITY;
CREATE POLICY booking_workspace ON shortlist.booking_clicks
    USING ((current_user='shortlist_worker' AND nullif(current_setting('shortlist.workspace_id',true),'') IS NULL)
        OR workspace_id=nullif(current_setting('shortlist.workspace_id',true),'')::uuid)
    WITH CHECK ((current_user='shortlist_worker' AND nullif(current_setting('shortlist.workspace_id',true),'') IS NULL)
        OR workspace_id=nullif(current_setting('shortlist.workspace_id',true),'')::uuid);
GRANT SELECT,INSERT,DELETE ON shortlist.booking_clicks TO shortlist_api,shortlist_worker;
