"""Deterministic Royalty Consensus Suite.

Guards the property the steward requires: every leader result a validator node
accepts must carry the exact same clearance decision and the exact same royalty
split. These tests drive the contract's real captured validator_fn through
gltest's direct-mode replay, re-mocking the fingerprint and LLM feeds between
the leader run and the validator run to simulate two nodes scoring the same pair
of tracks slightly differently.

Three directions are covered:
  SAFETY   - no pair of scores that disagree on the split is ever accepted.
  LIVENESS - scores that agree on the split are not spuriously rejected.
  EVIDENCE - nodes that fetched different audio never reach agreement at all.
"""

import json

import pytest
from conftest import (
    ATTO,
    CONTRACT_PATH,
    DERIVATIVE_DOC,
    MASTER_DOC,
    create_agreement,
    mock_full_audit,
    register_work,
)

SAMPLE_SEC = 30
TOTAL_SEC = 150  # 20% sample weight -> 80% band scaling


def _prepare(direct_vm, direct_deploy, alice, bob, sample_sec=SAMPLE_SEC, total_sec=TOTAL_SEC):
    contract = direct_deploy(CONTRACT_PATH)
    register_work(contract, direct_vm, alice, work_id="work-det")
    create_agreement(
        contract,
        direct_vm,
        bob,
        agreement_id="aggr-det",
        work_id="work-det",
        sample_sec=sample_sec,
        total_sec=total_sec,
        deposit_atto=5 * ATTO,
    )
    return contract


def _clear_then_validate(
    direct_vm,
    direct_deploy,
    alice,
    bob,
    leader_score,
    validator_score,
    leader_decision="APPROVED",
    validator_decision="APPROVED",
    validator_master_doc=MASTER_DOC,
    validator_derivative_doc=DERIVATIVE_DOC,
):
    """Clear with the leader's reading, then replay validator_fn with another.

    Returns (validator_accepted, settled_split_bps, settled_status).
    """
    contract = _prepare(direct_vm, direct_deploy, alice, bob)

    mock_full_audit(direct_vm, decision=leader_decision, similarity_score=leader_score)
    contract.evaluate_sample_clearance("aggr-det")
    settled = contract.get_agreement("aggr-det")

    # The validator node now scores the same pair of tracks for itself.
    direct_vm.clear_mocks()
    mock_full_audit(
        direct_vm,
        decision=validator_decision,
        similarity_score=validator_score,
        master_doc=validator_master_doc,
        derivative_doc=validator_derivative_doc,
    )
    accepted = direct_vm.run_validator()

    return accepted, settled["royalty_split_bps"], settled["status"]


# -----------------------------------------------------------------------------
# 1. Tier tables: the split is a step function, flat inside every band
# -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "score,expected_bps,expected_decision",
    [
        (0, 0, "REJECTED"),
        (39, 0, "REJECTED"),      # below the clearance floor
        (40, 1200, "APPROVED"),   # tier 1500 * band 8000 // 10000
        (54, 1200, "APPROVED"),   # last score of the 40-54 tier
        (55, 2000, "APPROVED"),   # tier 2500
        (69, 2000, "APPROVED"),
        (70, 2800, "APPROVED"),   # tier 3500
        (84, 2800, "APPROVED"),
        (85, 4000, "APPROVED"),   # tier 5000
        (100, 4000, "APPROVED"),
    ],
)
def test_tier_table_is_a_step_function(
    direct_vm, direct_deploy, direct_alice, score, expected_bps, expected_decision
):
    contract = direct_deploy(CONTRACT_PATH)
    quote = contract.preview_royalty_split(score, SAMPLE_SEC, TOTAL_SEC)

    assert quote["decision"] == expected_decision
    assert quote["royalty_split_bps"] == expected_bps


def test_split_is_flat_across_every_score_in_a_band(direct_vm, direct_deploy, direct_alice):
    """Every score inside one tier must yield a byte-identical split."""
    contract = direct_deploy(CONTRACT_PATH)

    for band_start, band_end in [(40, 54), (55, 69), (70, 84), (85, 100)]:
        splits = {
            contract.preview_royalty_split(s, SAMPLE_SEC, TOTAL_SEC)["royalty_split_bps"]
            for s in range(band_start, band_end + 1)
        }
        assert len(splits) == 1, f"tier {band_start}-{band_end} is not flat: {splits}"


def test_royalty_quote_is_reproducible(direct_vm, direct_deploy, direct_alice):
    """Repeated evaluation of the same input never drifts."""
    contract = direct_deploy(CONTRACT_PATH)
    quotes = {
        json.dumps(contract.preview_royalty_split(73, SAMPLE_SEC, TOTAL_SEC), sort_keys=True)
        for _ in range(50)
    }
    assert len(quotes) == 1


def test_tier_tables_are_exposed_and_ordered(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT_PATH)

    tiers = contract.get_similarity_tiers()
    assert len(tiers) == 4
    floors = [t["min_similarity_score"] for t in tiers]
    splits = [t["base_split_bps"] for t in tiers]
    assert floors == sorted(floors, reverse=True), "tiers must descend for first-match to be correct"
    assert splits == sorted(splits, reverse=True), "higher similarity must never pay less"
    assert floors[-1] == contract.get_protocol_overview()["min_clearance_similarity"]

    bands = contract.get_sample_weight_bands()
    assert len(bands) == 3
    band_floors = [b["min_sample_weight_pct"] for b in bands]
    band_scales = [b["scaling_bps"] for b in bands]
    assert band_floors == sorted(band_floors, reverse=True)
    assert band_scales == sorted(band_scales, reverse=True)
    assert band_floors[-1] == 0, "lowest band must be total for any sample weight"


def test_split_always_within_protocol_bounds(direct_vm, direct_deploy, direct_alice):
    """No reachable (score, weight) pair may escape the 5%-50% envelope."""
    contract = direct_deploy(CONTRACT_PATH)

    for score in range(0, 101):
        for sample_sec, total_sec in [(1, 200), (10, 100), (30, 120), (95, 100), (100, 100)]:
            quote = contract.preview_royalty_split(score, sample_sec, total_sec)
            bps = quote["royalty_split_bps"]
            if quote["decision"] == "APPROVED":
                assert 500 <= bps <= 5000, f"score={score} weight={sample_sec}/{total_sec} -> {bps}"
            else:
                assert bps == 0


# -----------------------------------------------------------------------------
# 2. LIVENESS: scores inside one tier must reach consensus
# -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "leader,validator",
    [
        (80, 80),    # no drift
        (80, 81),    # 1 point  - previously accepted, still accepted
        (70, 84),    # 14 points, same tier
        (85, 100),   # 15 points, both top tier - previously rejected by the drift rule
        (40, 54),    # both lowest cleared tier
        (55, 69),    # both mid tier
        (0, 39),     # both below the clearance floor, both reject
        (5, 30),     # 25 points apart, identical zero split
    ],
)
def test_agreeing_scores_reach_consensus(
    direct_vm, direct_deploy, direct_alice, direct_bob, leader, validator
):
    accepted, split, _ = _clear_then_validate(
        direct_vm, direct_deploy, direct_alice, direct_bob, leader, validator
    )
    assert accepted is True, (
        f"leader={leader} validator={validator} settle to the same split "
        f"({split} bps) but consensus was rejected"
    )


def test_rejection_reason_disagreement_still_reaches_consensus(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    """One node rejects outright, the other scores below the floor.

    Both settle to a zero split and a refund, so the money is identical and the
    result must be accepted.
    """
    accepted, split, status = _clear_then_validate(
        direct_vm, direct_deploy, direct_alice, direct_bob,
        leader_score=10, validator_score=25,
        leader_decision="REJECTED", validator_decision="APPROVED",
    )
    assert accepted is True
    assert split == 0
    assert status == "REJECTED"


# -----------------------------------------------------------------------------
# 3. SAFETY: scores that disagree on the split must never be accepted
# -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "leader,validator,reason",
    [
        (39, 40, "no clearance vs 12% split"),
        (54, 55, "12% vs 20%"),
        (69, 70, "20% vs 28%"),
        (84, 85, "28% vs 40%"),
        (10, 95, "no clearance vs top tier"),
        (60, 90, "mid tier vs top tier"),
    ],
)
def test_divergent_splits_are_rejected(
    direct_vm, direct_deploy, direct_alice, direct_bob, leader, validator, reason
):
    accepted, _, _ = _clear_then_validate(
        direct_vm, direct_deploy, direct_alice, direct_bob, leader, validator
    )
    assert accepted is False, f"accepted a divergent royalty split ({reason})"


def test_decision_disagreement_that_changes_payout_is_rejected(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    """Leader clears at the top tier, validator rejects the sample outright."""
    accepted, _, _ = _clear_then_validate(
        direct_vm, direct_deploy, direct_alice, direct_bob,
        leader_score=90, validator_score=90,
        leader_decision="APPROVED", validator_decision="REJECTED",
    )
    assert accepted is False


def _oracle_settlement(score):
    """Expected (decision, split_bps) at SAMPLE_SEC/TOTAL_SEC, written out by hand.

    Deliberately independent of the contract's tier tables: the values are
    literals, not derived from SIMILARITY_TIERS. If the contract's tiers drift,
    this disagrees instead of drifting along with them.

    At 30/150 the sample weight is 20%, which scales every tier by 8000 bps.
    """
    if score < 40:
        return ("REJECTED", 0)
    if score < 55:
        return ("APPROVED", 1200)   # 1500 * 8000 // 10000
    if score < 70:
        return ("APPROVED", 2000)   # 2500 * 8000 // 10000
    if score < 85:
        return ("APPROVED", 2800)   # 3500 * 8000 // 10000
    return ("APPROVED", 4000)       # 5000 * 8000 // 10000


def test_contract_split_matches_independent_oracle(direct_vm, direct_deploy, direct_alice):
    """The contract's own quote must equal a hand-written tier table."""
    contract = direct_deploy(CONTRACT_PATH)

    mismatches = []
    for score in range(0, 101):
        quote = contract.preview_royalty_split(score, SAMPLE_SEC, TOTAL_SEC)
        actual = (quote["decision"], quote["royalty_split_bps"])
        expected = _oracle_settlement(score)
        if actual != expected:
            mismatches.append((score, actual, expected))

    assert mismatches == [], f"contract disagrees with the oracle: {mismatches}"


def test_no_accepted_pair_ever_differs_on_the_split(direct_vm, direct_deploy, direct_alice):
    """Exhaustive sweep of the steward's exact invariant.

    Over every pair of similarity scores in 0..100, assert the implication:
        validator accepts  =>  identical decision and identical royalty split.

    Acceptance is modelled by the independent oracle above rather than by the
    contract's own output, so the implication has real content: a contract whose
    tier boundaries sat elsewhere would produce a pair the oracle calls
    equivalent but the contract splits differently, and that shows up here.
    """
    contract = direct_deploy(CONTRACT_PATH)
    quotes = {s: contract.preview_royalty_split(s, SAMPLE_SEC, TOTAL_SEC) for s in range(0, 101)}

    violations = []
    for leader in range(0, 101):
        for validator in range(0, 101):
            # Would two nodes reading these scores be allowed to agree?
            if _oracle_settlement(leader) != _oracle_settlement(validator):
                continue
            lq, vq = quotes[leader], quotes[validator]
            if (lq["decision"], lq["royalty_split_bps"]) != (vq["decision"], vq["royalty_split_bps"]):
                violations.append((leader, validator, lq, vq))

    assert violations == [], f"split divergence among accepted pairs: {violations}"


# -----------------------------------------------------------------------------
# 4. EVIDENCE: nodes must have fetched the same audio to agree
# -----------------------------------------------------------------------------
def test_validator_that_fetched_different_master_audio_rejects(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    """Identical scores are not enough if the two nodes audited different bytes."""
    accepted, _, _ = _clear_then_validate(
        direct_vm, direct_deploy, direct_alice, direct_bob,
        leader_score=80, validator_score=80,
        validator_master_doc='{"format": "chromaprint", "vector": [4, 4, 4, 4]}',
    )
    assert accepted is False


def test_validator_that_fetched_different_derivative_audio_rejects(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    accepted, _, _ = _clear_then_validate(
        direct_vm, direct_deploy, direct_alice, direct_bob,
        leader_score=80, validator_score=80,
        validator_derivative_doc='{"format": "chromaprint", "vector": [7, 7, 7, 7]}',
    )
    assert accepted is False


def test_matching_evidence_and_matching_tier_is_accepted(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    """Control for the two tests above: same bytes and same tier still passes."""
    accepted, split, status = _clear_then_validate(
        direct_vm, direct_deploy, direct_alice, direct_bob,
        leader_score=80, validator_score=84,
    )
    assert accepted is True
    assert split == 2800
    assert status == "APPROVED_ACTIVE"


# -----------------------------------------------------------------------------
# 5. Sample-weight bands are threshold-relative and share one table
# -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "sample_sec,total_sec,expected_weight,expected_scaling",
    [
        (30, 100, 30, 10000),   # 30% -> top band
        (25, 100, 25, 10000),   # exactly at the top band floor
        (24, 100, 24, 8000),    # just under
        (10, 100, 10, 8000),    # at the middle band floor
        (9, 100, 9, 6000),      # just under
        (1, 200, 0, 6000),      # rounds to 0% -> lowest band
    ],
)
def test_sample_weight_bands_are_discrete(
    direct_vm, direct_deploy, direct_alice, sample_sec, total_sec, expected_weight, expected_scaling
):
    contract = direct_deploy(CONTRACT_PATH)
    quote = contract.preview_royalty_split(85, sample_sec, total_sec)

    assert quote["sample_weight_pct"] == expected_weight
    # Top similarity tier is 5000 bps, so the split reads the scaling directly.
    assert quote["royalty_split_bps"] == (5000 * expected_scaling) // 10000


def test_identical_sample_weight_gives_identical_split_across_track_lengths(
    direct_vm, direct_deploy, direct_alice
):
    """Two tracks sampled to the same percentage settle identically."""
    contract = direct_deploy(CONTRACT_PATH)

    short_track = contract.preview_royalty_split(80, 30, 150)   # 20%
    long_track = contract.preview_royalty_split(80, 120, 600)   # 20%
    assert short_track == long_track
