# Semantic verification

The extraction model previously matched “Consultancies without a software product” from Smeron's product-studio description. The exact quote existed, but the negative clause was not established. A stricter extraction prompt repeated that error. Citation existence alone cannot determine fit.

The worker now sends an independent verification request containing the original proposed assessment, its complete condition and source snapshots. It checks criterion polarity, every compound clause, entity, dates, negation and evidence claims. Only an `entailed` judgment preserves an observation. Unsupported, uncertain or missing judgments become unknown. Transport/schema failure and exhausted verification budgets also preserve sources while returning unknowns. Unknown or duplicate assessment IDs fail validation. All-unknown records skip inference.

Verification shares the eight-model-attempt run cap with extraction and repair. It is journaled separately as `verify:DOMAIN`; saved outcomes replay without a request. The run checkpoint contains audit judgments, while the original extraction stays in the operator's local result journal. Human acceptance remains separate from model qualification.

## Measured results

`examples/evaluation/semantic-cases.json` contains 30 engineering-labelled cases: 29 authored synthetic examples and the real Smeron excerpt. They cover direct evidence, negation, wrong entities, discontinued/future products, recurring services versus software, private ownership, founding dates, headquarters, compound exclusions and invented buying intent. Labels assess the complete proposed finding, not the actual commercial suitability of a company.

The actual `gemma-4-31B-it` verifier with policy 2 returned the expected decision on all 30 final cases: zero false acceptances, zero false rejections and zero provider/schema errors. Its actual judgments and reasons are saved in `examples/evaluation/gemma-verifier-2026-10-14.json`, with a corpus hash. Two contradiction claims were clarified and rerun; their earlier results were excluded. The software tests separately prove gate projection and failure handling; mocked judgments are not used as a model-accuracy measurement.

This small corpus is authored by the implementer and is not an independent benchmark. Passing it does not guarantee semantic accuracy on arbitrary companies, establish private ownership, or validate search/extraction quality. A different Gemma checkpoint has not been compared. Human review and larger held-out cases remain necessary.

Fresh assisted discovery `e09d48680f454ddcb14f1d6038fbe530` separately tested the full saved Smeron page with policy 1. Extraction again proposed the unsupported compound exclusion; verification rejected it and the final record is unknown. Prismatic retains three cited findings, with ownership/listing unknown. B2B Hub remains a fetch failure. Four real model requests (two extractions, two verifications), two fetched sources and three partial records are saved. Search metadata was imported, not obtained through the live Tavily/SerpApi adapters.

## Repeatable checks

```sh
python -m pytest -q tests/test_verification.py tests/test_journal.py tests/test_model_repair.py
python scripts/evaluate_semantics.py --database data/new-semantic-evaluation.sqlite3 --output data/new-semantic-evaluation.json --max-calls 30
python scripts/verify_saved_run.py e09d48680f454ddcb14f1d6038fbe530
```

The model evaluation requires configured Gemma credentials and makes up to 30 real requests in its dedicated database. Each request reserves an attempt and journals its result; rerunning against that database replays completed cases. It never silently retries an uncertain dispatch. Keep operator databases and credentials out of Git. The saved-run check makes no provider requests.
