ALTER TABLE shortlist.workspaces ADD COLUMN free_profiles INTEGER NOT NULL DEFAULT 0 CHECK(free_profiles>=0);
ALTER TABLE shortlist.workspaces ADD COLUMN profile_day DATE NOT NULL DEFAULT CURRENT_DATE;
ALTER TABLE shortlist.workspaces ADD COLUMN daily_profiles INTEGER NOT NULL DEFAULT 0 CHECK(daily_profiles>=0);
ALTER TABLE shortlist.runs ADD COLUMN legacy_credit_exempt BOOLEAN NOT NULL DEFAULT FALSE;
UPDATE shortlist.runs r SET legacy_credit_exempt=TRUE
    FROM shortlist.workspaces w WHERE r.workspace_id=w.id AND w.demo_run_id=r.id;
