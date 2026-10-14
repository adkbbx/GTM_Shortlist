-- Scheduler transactions have no workspace. Assigned research transactions
-- must obey the same owner scope as API transactions, including source reuse.
DO $$ DECLARE table_name TEXT; policy_name TEXT; BEGIN
    FOREACH table_name IN ARRAY ARRAY['runs','records','attempts','attempt_results','source_cache','run_events',
                                     'credit_entries','credit_reservations'] LOOP
        policy_name := CASE WHEN table_name IN ('credit_entries','credit_reservations')
                            THEN 'credit_workspace' ELSE 'workspace_scope' END;
        EXECUTE format('DROP POLICY %I ON shortlist.%I',policy_name,table_name);
        EXECUTE format('CREATE POLICY %I ON shortlist.%I USING '
            '((current_user=''shortlist_worker'' AND nullif(current_setting(''shortlist.workspace_id'',true),'''') IS NULL) '
            'OR workspace_id=nullif(current_setting(''shortlist.workspace_id'',true),'''')::uuid) '
            'WITH CHECK ((current_user=''shortlist_worker'' AND nullif(current_setting(''shortlist.workspace_id'',true),'''') IS NULL) '
            'OR workspace_id=nullif(current_setting(''shortlist.workspace_id'',true),'''')::uuid)',policy_name,table_name);
    END LOOP;
END $$;
DROP POLICY owner_workspace ON shortlist.workspaces;
CREATE POLICY owner_workspace ON shortlist.workspaces
    USING ((current_user='shortlist_worker' AND nullif(current_setting('shortlist.workspace_id',true),'') IS NULL)
        OR id=nullif(current_setting('shortlist.workspace_id',true),'')::uuid)
    WITH CHECK ((current_user='shortlist_worker' AND nullif(current_setting('shortlist.workspace_id',true),'') IS NULL)
        OR id=nullif(current_setting('shortlist.workspace_id',true),'')::uuid);
