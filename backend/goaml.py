"""goAML STR export — serialize a structured STRDraft into the regulator's wire
format (the integration seam; see docs/plan-goaml-integration.md).

Pure and deterministic (no LLM, no network), so it is safe on the filmed demo's
critical path (ADR-0003). Transaction-based STR report: each cited transaction
becomes one <transaction>, with the from/to parties keyed by the movement's
`direction` (the subject account is always the reporting bank's "my client" side).

The built document is validated against the checked-in, tightly-scoped goAML XSD
*before* it is returned: a non-conforming report can never leave this module.
Institution-level constants (rentity_id, codes, reporting officer) come from
`data/goaml_config.json` — the seam that graduates this faithful derivation to
literal per-FIU conformance without code changes.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from lxml import etree
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from schemas import STRDraft, Transaction

_DATA = Path(__file__).resolve().parent / "data"
_XSD_PATH = _DATA / "goaml_str.xsd"

_UNKNOWN = "UNKNOWN"


_CONFIG = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class ReportingPerson(BaseModel):
    model_config = _CONFIG
    first_name: str
    last_name: str


class GoamlConfig(BaseModel):
    """Per-FIU institution registration. Loaded from data/goaml_config.json; the
    only place real-vs-stub values live (decision #8). camelCase on disk."""

    model_config = _CONFIG
    rentity_id: int
    entity_reference: str
    submission_code: str
    report_code: str
    currency_code_local: str
    local_country_code: str
    funds_code: str
    reporting_person: ReportingPerson


def submission_reference(alert_id: str) -> str:
    """A demo-stable FIU acknowledgement reference for a filed STR (ADR-0003):
    deterministic in the alert id, so re-filing the same alert yields the same ref."""
    seq = int(hashlib.sha256(alert_id.encode()).hexdigest(), 16) % 1_000_000
    return f"MYFIU-2026-{seq:06d}"


@lru_cache(maxsize=1)
def _schema() -> etree.XMLSchema:
    return etree.XMLSchema(etree.parse(str(_XSD_PATH)))


def _sub(parent: etree._Element, tag: str, text: str) -> etree._Element:
    el = etree.SubElement(parent, tag)
    el.text = text
    return el


def _account(parent: etree._Element, tag: str, institution: str, number: str, name: str) -> None:
    acc = etree.SubElement(parent, tag)
    _sub(acc, "institution_name", institution)
    _sub(acc, "account", number)
    _sub(acc, "account_name", name)


def _transaction_el(
    report: etree._Element,
    cited,
    txn: Transaction | None,
    *,
    institution: str,
    subject_account: str,
    subject_name: str,
    config: GoamlConfig,
) -> None:
    """One <transaction>. The subject account is the reporting bank's customer, so
    it is the *_my_client side; the counterparty is the plain t_from / t_to side.
    Direction decides which way round (default inbound if the full txn is absent)."""
    direction = txn.direction if txn else "inbound"
    channel = txn.channel if txn else "transfer"
    cp_name = txn.counterparty_name if txn else cited.counterparty_name
    cp_account = (txn.counterparty_account if txn else None) or _UNKNOWN
    cp_bank = (txn.counterparty_bank if txn else None) or _UNKNOWN

    el = etree.SubElement(report, "transaction")
    _sub(el, "transactionnumber", cited.transaction_id)
    _sub(el, "date_transaction", cited.timestamp.isoformat())
    _sub(el, "transmode_code", channel)
    _sub(el, "amount_local", f"{cited.amount:.2f}")

    # Originating party.
    if direction == "inbound":
        t_from = etree.SubElement(el, "t_from")  # counterparty sends in
        _sub(t_from, "from_funds_code", config.funds_code)
        _sub(t_from, "from_country", config.local_country_code)
        _account(t_from, "from_account", cp_bank, cp_account, cp_name)
    else:
        t_from = etree.SubElement(el, "t_from_my_client")  # our customer sends out
        _sub(t_from, "from_funds_code", config.funds_code)
        _sub(t_from, "from_country", config.local_country_code)
        _account(t_from, "from_account", institution, subject_account, subject_name)

    # Beneficiary party.
    if direction == "inbound":
        t_to = etree.SubElement(el, "t_to_my_client")  # our customer receives
        _sub(t_to, "to_funds_code", config.funds_code)
        _sub(t_to, "to_country", config.local_country_code)
        _account(t_to, "to_account", institution, subject_account, subject_name)
    else:
        t_to = etree.SubElement(el, "t_to")  # counterparty receives
        _sub(t_to, "to_funds_code", config.funds_code)
        _sub(t_to, "to_country", config.local_country_code)
        _account(t_to, "to_account", cp_bank, cp_account, cp_name)


def to_goaml_str_xml(
    str_draft: STRDraft,
    transactions: list[Transaction],
    config: GoamlConfig,
    *,
    submission_date: datetime,
) -> bytes:
    """Serialize an (approved) STRDraft to a schema-valid goAML STR report.

    `transactions` is the alert's full transaction list, used to recover the
    direction / channel / counterparty account that the cited-transaction summary
    drops. Raises ValueError if the result fails XSD validation."""
    by_id = {t.transaction_id: t for t in transactions}

    report = etree.Element("report")
    _sub(report, "rentity_id", str(config.rentity_id))
    _sub(report, "submission_code", config.submission_code)
    _sub(report, "report_code", config.report_code)
    _sub(report, "entity_reference", config.entity_reference)
    _sub(report, "submission_date", submission_date.isoformat())
    _sub(report, "currency_code_local", config.currency_code_local)

    rp = etree.SubElement(report, "reporting_person")
    _sub(rp, "first_name", config.reporting_person.first_name)
    _sub(rp, "last_name", config.reporting_person.last_name)

    # The narrative: AI-drafted summary plus the analyst's grounds, as one reason.
    reason = str_draft.activity_summary
    if str_draft.grounds_for_suspicion:
        reason += "\n\nGrounds for suspicion:\n" + "\n".join(
            f"- {g}" for g in str_draft.grounds_for_suspicion
        )
    _sub(report, "reason", reason)
    _sub(report, "action", str_draft.recommended_action)

    institution = str_draft.reporting_institution
    subject = str_draft.subject
    for cited in str_draft.cited_transactions:
        _transaction_el(
            report,
            cited,
            by_id.get(cited.transaction_id),
            institution=institution,
            subject_account=subject.account_id,
            subject_name=subject.holder_name,
            config=config,
        )

    # matchedTypology.code -> indicator (FIU code lists are configurable; decision #5).
    indicators = etree.SubElement(report, "report_indicators")
    _sub(indicators, "indicator", str_draft.typology.code)

    schema = _schema()
    if not schema.validate(report):
        raise ValueError(f"goAML report failed XSD validation: {schema.error_log}")

    return etree.tostring(report, pretty_print=True, xml_declaration=True, encoding="UTF-8")
