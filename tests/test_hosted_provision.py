from urllib.parse import urlsplit

import pytest
from dotenv import dotenv_values
from psycopg.conninfo import conninfo_to_dict

from scripts.provision_hosted import private_env, runtime_uri


def test_pooler_runtime_credentials_replace_operator_and_encode_password():
    operator = "postgresql://postgres.project:operator-secret@aws-0-example.pooler.supabase.com:5432/postgres?sslmode=prefer"
    uri = runtime_uri(operator, "shortlist_api_login", "a@b:/#' %+secret", "project")
    parsed = conninfo_to_dict(uri)
    assert parsed["user"] == "shortlist_api_login.project"
    assert parsed["password"] == "a@b:/#' %+secret"
    assert parsed["sslmode"] == "require"
    assert "operator-secret" not in uri and "postgres.project" not in uri


def test_direct_connection_has_no_pooler_username_suffix():
    uri = runtime_uri("postgresql://postgres:operator-secret@db.project.supabase.co/postgres",
                      "shortlist_worker_login", "generated-password", "project")
    assert conninfo_to_dict(uri)["user"] == "shortlist_worker_login"
    assert urlsplit(uri).hostname == "db.project.supabase.co"


@pytest.mark.parametrize("uri", ["postgresql://postgres.other:secret@aws-0-example.pooler.supabase.com/postgres",
                                 "postgresql://postgres:secret@db.other.supabase.co/postgres"])
def test_runtime_credentials_do_not_silently_switch_projects(uri):
    with pytest.raises(ValueError):
        runtime_uri(uri, "shortlist_api_login", "new-password", "project")


def test_private_environment_roundtrip_and_replacement(tmp_path):
    path = tmp_path / "api.env"
    values = {"SHORTLIST_DATABASE_URL": "postgresql://login:a%40b@database.example/postgres?sslmode=require",
              "SUPABASE_PUBLISHABLE_KEY": "sb_publishable_fixture"}
    private_env(path, values)
    assert dotenv_values(path) == values
    private_env(path, values)
    assert dotenv_values(path) == values
    assert not path.with_suffix(".pending").exists()
