"""Farm references never substitute for source evidence or authorize invented claims."""
import pytest

from src.agent.companion.graph import validate_claims
from src.integrations.contracts import ConnectorError

EVIDENCE = "22222222-2222-4222-8222-222222222222"
PLOT = "91378aaf-b284-4703-bc6d-4b369eb0bec5"
FOREIGN = "33333333-3333-4333-8333-333333333333"
OUTCOMES = [{"evidence_ids": [EVIDENCE], "data": {"rain_mm": 5}, "source": {}}]


def test_authorized_farm_reference_and_real_evidence_citation_are_distinct():
    validate_claims(f"Farm {PLOT}: forecast rain 5 mm. Evidence: {EVIDENCE}", OUTCOMES, context_ids=[PLOT])


def test_authorized_farm_reference_alone_cannot_replace_evidence():
    with pytest.raises(ConnectorError, match="must cite evidence"):
        validate_claims(f"Farm {PLOT}: forecast rain 5 mm.", OUTCOMES, context_ids=[PLOT])


def test_unknown_farm_or_evidence_reference_stays_blocked():
    with pytest.raises(ConnectorError, match="absent from this run"):
        validate_claims(f"Farm {FOREIGN}: forecast rain 5 mm. Evidence: {EVIDENCE}", OUTCOMES, context_ids=[PLOT])


def test_authorized_context_does_not_allow_invented_numbers():
    with pytest.raises(ConnectorError, match="numerical value absent"):
        validate_claims(f"Farm {PLOT}: forecast rain 999 mm. Evidence: {EVIDENCE}", OUTCOMES, context_ids=[PLOT])


def test_markdown_section_and_list_ordinals_are_not_measurements():
    validate_claims(f"## 2. Weather\n1. Forecast rain 5 mm. Evidence: {EVIDENCE}", OUTCOMES)


def test_actual_retrieval_timestamp_is_authoritative_metadata():
    outcomes = [{**OUTCOMES[0], "retrieved_at": "2026-11-17T07:31:16.362536+00:00"}]
    validate_claims(f"Retrieved 2026-11-17T07:31:16.362536+00:00. Evidence: {EVIDENCE}", outcomes)
    with pytest.raises(ConnectorError, match="numerical value absent"):
        validate_claims(f"Retrieved 2026-11-17T07:31:999.999+00:00. Evidence: {EVIDENCE}", outcomes)


def test_numbered_heading_does_not_hide_an_invented_measurement():
    with pytest.raises(ConnectorError, match="numerical value absent"):
        validate_claims(f"## 2. Forecast rain 999 mm\nEvidence: {EVIDENCE}", OUTCOMES)
