"""Generate authoritative API schema and JSON schemas for client runtime validation."""
import json
from pathlib import Path

from pydantic import TypeAdapter

from shortlist.api import (
    AuthSetup,
    Health,
    RunView,
    ServiceView,
    WalletView,
    create_app,
)

root = Path(__file__).resolve().parents[1]
(root / "web/generated").mkdir(parents=True, exist_ok=True)
(root / "web/generated/openapi.json").write_text(json.dumps(create_app().openapi(), indent=2), encoding="utf-8")
for model in (RunView, Health, WalletView, ServiceView):
    (root / f"web/generated/{model.__name__}.json").write_text(json.dumps(model.model_json_schema(mode="serialization"), indent=2), encoding="utf-8")
(root / "web/generated/AuthSetup.json").write_text(
    json.dumps(TypeAdapter(AuthSetup).json_schema(mode="serialization"), indent=2), encoding="utf-8")
