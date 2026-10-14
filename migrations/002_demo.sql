-- No foreign key: deleting research must not grant another free run.
ALTER TABLE shortlist.workspaces ADD COLUMN demo_run_id TEXT;
CREATE INDEX runs_workspace_order ON shortlist.runs(workspace_id,created_at,position);
CREATE INDEX events_workspace_run ON shortlist.run_events(workspace_id,run_id,id);
