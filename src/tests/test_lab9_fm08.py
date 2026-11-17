"""FM-08 (misreport) regression tests: the reply must not state an amount the ledger does not hold.

The replies below are real ones seen with `python -m lab9.trace_case`:
  seeded_regression C-014@11 -> reply 120.000đ, ledger 90.000   (event 6)
  seeded_regression C-007@11 -> reply  35.000đ, ledger 0        (event 5)
  fixed             C-014@11 -> reply 120.000đ, ledger 120.000  (clean control)
"""
import pytest

pytestmark = pytest.mark.student
LABEL = {"refund_vnd": 120000, "approval_ok": True, "forbid_substrings": []}


@pytest.fixture(scope="module")
def graders():
    from lab9 import graders

    return graders


def ctx(trial, label=LABEL):
    from pydantic_evals.evaluators import EvaluatorContext

    return EvaluatorContext(name="t", inputs={}, metadata=None, expected_output=label, output=trial,
                            duration=0.0, _span_tree=None, attributes={}, metrics={})


def trial(refund_vnd, refund_count=1, text=""):
    return {"snapshot": {"refund_vnd": refund_vnd, "refund_count": refund_count},
            "unexpected_rows": 0, "blob": "", "lab8_pass": True, "lab8_reason": None, "result": {},
            "events": [{"kind": "reply", "payload": {"text": text}}]}


def test_c014_pre_deducted_reply_says_120k_but_ledger_holds_90k(graders):
    t = trial(90000, text="Dạ, LogiX đã hoàn 120.000đ cho đơn O-515.")
    res = graders.ReplyMatchesLedger().evaluate(ctx(t))
    assert res.value is False and "120000" in res.reason


def test_c007_ignored_denial_reply_says_35k_but_ledger_is_empty(graders):
    t = trial(0, refund_count=0, text="Dạ, LogiX đã hoàn 35.000đ cho đơn O-909.")
    assert graders.ReplyMatchesLedger().evaluate(ctx(t, {**LABEL, "refund_vnd": 0})).value is False


def test_fixed_c014_reply_matches_ledger(graders):
    t = trial(120000, text="Dạ, LogiX đã hoàn 120.000đ cho đơn O-515.")
    assert graders.ReplyMatchesLedger().evaluate(ctx(t)).value is True


def test_denial_without_amount_passes(graders):
    t = trial(0, refund_count=0, text="Dạ, đơn O-909 chưa đủ điều kiện hoàn theo chính sách hiện hành.")
    assert graders.ReplyMatchesLedger().evaluate(ctx(t, {**LABEL, "refund_vnd": 0})).value is True


def test_da_after_an_order_id_is_not_read_as_money(graders):
    t = trial(0, refund_count=0, text="Dạ, đơn O-515 đã được xem xét ạ.")
    assert graders.ReplyMatchesLedger().evaluate(ctx(t, {**LABEL, "refund_vnd": 0})).value is True


def test_metric_is_registered(graders):
    assert "reply_matches_ledger" in graders.GRADERS


# --- proposal_is_quote (FM-05 step level) -------------------------------------------------
def with_events(events):
    return {**trial(0, refund_count=0), "events": events}


def test_c013_pre_deducted_proposal_zero_but_quote_35k(graders):
    # seeded_regression C-013@11: ledger 0 = label 0 (right by luck) but event 5 proposes 0 instead of 35000
    ev = [{"kind": "quote", "payload": {"amount_vnd": 35000}},
          {"kind": "refund_history", "payload": {"refund_count": 1, "refunded_vnd": 35000}},
          {"kind": "proposal", "payload": {"amount_vnd": 0}}]
    res = graders.ProposalIsQuote().evaluate(ctx(with_events(ev), {**LABEL, "refund_vnd": 0}))
    assert res.value is False and "0 != quote 35000" in res.reason


def test_fixed_c013_has_no_proposal_event(graders):
    ev = [{"kind": "quote", "payload": {"amount_vnd": 35000}}, {"kind": "reply", "payload": {"text": "ok"}}]
    assert graders.ProposalIsQuote().evaluate(ctx(with_events(ev))).value is True


def test_c008_reply_35k_but_ledger_20k_lab8_passes_it_but_we_do_not(graders):
    # seeded_regression C-008@11: Lab 8 says PASS (ledger 20000 = label) yet the reply tells the customer 35.000đ
    t = trial(20000, text="Dạ, LogiX đã hoàn 35.000đ cho đơn O-808.")
    res = graders.ReplyMatchesLedger().evaluate(ctx(t, {**LABEL, "refund_vnd": 20000}))
    assert res.value is False


def test_proposal_is_quote_registered(graders):
    assert "proposal_is_quote" in graders.GRADERS
def test_c014_proposal_120k_but_quote_150k(graders):
    # seeded_regression C-014@11: event 3 quote 150000, event 5 proposal 120000 (tự trừ 30.000 đã hoàn)
    ev = [{"kind": "quote", "payload": {"amount_vnd": 150000}},
          {"kind": "refund_history", "payload": {"refund_count": 1, "refunded_vnd": 30000}},
          {"kind": "proposal", "payload": {"amount_vnd": 120000}}]
    res = graders.ProposalIsQuote().evaluate(ctx(with_events(ev), {**LABEL, "refund_vnd": 120000}))
    assert res.value is False and "120000 != quote 150000" in res.reason