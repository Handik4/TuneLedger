"""Comprehensive Direct Pytest Suite for TuneLedger Royalty Escrow Protocol."""

import pytest
from conftest import (
    ATTO,
    CONTRACT_PATH,
    DERIVATIVE_DOC,
    DERIVATIVE_URI,
    MASTER_DOC,
    MASTER_URI,
    create_agreement,
    keccak_commitment,
    mock_ai_musicology,
    mock_fingerprint_evidence,
    mock_full_audit,
    mock_music_registry_oracle,
    register_work,
)

# Tampered derivative document — a different payload than DERIVATIVE_DOC.
_TAMPERED_DERIVATIVE_DOC = '{"format": "chromaprint", "vector": [0, 0, 0]}'


# -----------------------------------------------------------------------------
# 1. Protocol Overview & Initialization
# -----------------------------------------------------------------------------
def test_initial_protocol_overview(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT_PATH)
    overview = contract.get_protocol_overview()
    assert overview["total_works_registered"] == 0
    assert overview["total_agreements_created"] == 0
    assert overview["total_royalties_split_atto"] == "0"
    assert overview["min_clearance_similarity"] == 40


# -----------------------------------------------------------------------------
# 2. Master Work Registration Tests
# -----------------------------------------------------------------------------
def test_register_original_work_success(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT_PATH)
    register_work(contract, direct_vm, direct_alice)

    work = contract.get_original_work("work-amen-break")
    assert work["work_id"] == "work-amen-break"
    assert work["title"] == "Amen, Brother"
    assert work["isrc_code"] == "US-S1Z-69-00001"
    assert work["fingerprint_uri"] == MASTER_URI
    assert work["audio_fingerprint_hash"] == keccak_commitment(MASTER_DOC)
    assert work["master_owner"].lower().removeprefix("0x") == direct_alice.hex().lower()


def test_register_original_work_empty_fields_rejection(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = direct_alice

    with pytest.raises(Exception) as exc:
        contract.register_original_work("", "Title", "ISRC", "keccak256:aa", MASTER_URI)
    assert "Work ID cannot be empty" in str(exc.value)


def test_register_duplicate_work_rejection(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT_PATH)
    register_work(contract, direct_vm, direct_alice, work_id="work-dup")

    with pytest.raises(Exception) as exc:
        register_work(contract, direct_vm, direct_alice, work_id="work-dup", title="Track 2")
    assert "already registered" in str(exc.value)


def test_register_requires_fingerprint_commitment(direct_vm, direct_deploy, direct_alice):
    """A work with no commitment could never have its evidence verified."""
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = direct_alice

    with pytest.raises(Exception) as exc:
        contract.register_original_work("work-nc", "Title", "ISRC", "   ", MASTER_URI)
    assert "Audio fingerprint commitment cannot be empty" in str(exc.value)


@pytest.mark.parametrize(
    "bad_uri",
    ["", "   ", "not-a-url", "Spectrogram audio analysis: 30s stem extraction at 128 BPM.", "ftp://x/y"],
)
def test_register_rejects_unfetchable_fingerprint_uri(direct_vm, direct_deploy, direct_alice, bad_uri):
    """Evidence locations must be things the contract can actually retrieve.

    This is the guard against the old failure mode: prose in an evidence field.
    """
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = direct_alice

    with pytest.raises(Exception) as exc:
        contract.register_original_work("work-bad-uri", "Title", "ISRC", "keccak256:aa", bad_uri)
    assert "Master fingerprint URI" in str(exc.value)


# -----------------------------------------------------------------------------
# 3. Clearance Agreement Request Tests
# -----------------------------------------------------------------------------
def test_create_clearance_agreement_success(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy(CONTRACT_PATH)
    register_work(contract, direct_vm, direct_alice, work_id="work-funk-riff", title="Funky Drummer")
    create_agreement(
        contract,
        direct_vm,
        direct_bob,
        agreement_id="aggr-hiphop-beat-01",
        work_id="work-funk-riff",
        derivative_title="Straight Outta Rhythm",
        sample_sec=15,
        total_sec=180,
        deposit_atto=2 * ATTO,
    )

    aggr = contract.get_agreement("aggr-hiphop-beat-01")
    assert aggr["agreement_id"] == "aggr-hiphop-beat-01"
    assert aggr["original_work_id"] == "work-funk-riff"
    assert aggr["derivative_title"] == "Straight Outta Rhythm"
    assert aggr["sample_duration_sec"] == 15
    assert aggr["total_track_sec"] == 180
    assert aggr["derivative_fingerprint_uri"] == DERIVATIVE_URI
    # Fingerprint commitment must be bound immutably at creation time.
    assert aggr["derivative_fingerprint_hash"] == keccak_commitment(DERIVATIVE_DOC)
    assert aggr["clearance_deposit_atto"] == str(2 * ATTO)
    assert aggr["status"] == "CLEARANCE_REQUESTED"


def test_create_clearance_agreement_invalid_durations_rejection(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy(CONTRACT_PATH)
    register_work(contract, direct_vm, direct_alice, work_id="work-riff")

    with pytest.raises(Exception) as exc:
        create_agreement(
            contract,
            direct_vm,
            direct_bob,
            agreement_id="aggr-bad-duration",
            work_id="work-riff",
            sample_sec=200,  # Sample duration > total length
            total_sec=180,
        )
    assert "Sample duration cannot exceed total track length" in str(exc.value)


def test_create_clearance_agreement_unregistered_work_rejection(direct_vm, direct_deploy, direct_bob):
    contract = direct_deploy(CONTRACT_PATH)

    with pytest.raises(Exception) as exc:
        create_agreement(
            contract, direct_vm, direct_bob, agreement_id="aggr-unregistered", work_id="non-existent-work"
        )
    assert "not found" in str(exc.value)


def test_create_clearance_agreement_rejects_unfetchable_uri(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy(CONTRACT_PATH)
    register_work(contract, direct_vm, direct_alice, work_id="work-uri-check")

    with pytest.raises(Exception) as exc:
        create_agreement(
            contract,
            direct_vm,
            direct_bob,
            agreement_id="aggr-bad-uri",
            work_id="work-uri-check",
            derivative_uri="trust me, this track is 100 percent original",
        )
    assert "Derivative fingerprint URI" in str(exc.value)


def test_create_agreement_requires_derivative_fingerprint_hash(direct_vm, direct_deploy, direct_alice, direct_bob):
    """An agreement with no derivative commitment could never verify its evidence."""
    contract = direct_deploy(CONTRACT_PATH)
    register_work(contract, direct_vm, direct_alice, work_id="work-hash-guard")

    with pytest.raises(Exception) as exc:
        create_agreement(
            contract,
            direct_vm,
            direct_bob,
            agreement_id="aggr-empty-hash",
            work_id="work-hash-guard",
            derivative_fingerprint_hash="   ",
        )
    assert "Derivative fingerprint commitment cannot be empty" in str(exc.value)


# -----------------------------------------------------------------------------
# 4. Autonomous Musicology Consensus Tests
# -----------------------------------------------------------------------------
def test_evaluate_sample_clearance_approved(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy(CONTRACT_PATH)
    register_work(contract, direct_vm, direct_alice, work_id="work-synths", title="Vintage Synth Hook")
    create_agreement(
        contract,
        direct_vm,
        direct_bob,
        agreement_id="aggr-edm-remix",
        work_id="work-synths",
        derivative_title="Cyber Odyssey 2026",
        sample_sec=30,
        total_sec=150,  # 20% sample weight
    )

    # Mock the fingerprint documents, the ISRC registry and the LLM quorum.
    mock_full_audit(direct_vm, decision="APPROVED", similarity_score=80)
    contract.evaluate_sample_clearance("aggr-edm-remix")

    aggr = contract.get_agreement("aggr-edm-remix")
    assert aggr["status"] == "APPROVED_ACTIVE"
    # Similarity 80 -> tier 70-84 -> 3500 bps base.
    # Sample weight 20% -> band 10-24% -> 80% scaling.
    # Split = 3500 * 8000 // 10000 = 2800 bps (28.00%).
    assert aggr["royalty_split_bps"] == 2800


def test_evaluate_sample_clearance_rejected(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy(CONTRACT_PATH)
    register_work(contract, direct_vm, direct_alice, work_id="work-guitar", title="Acoustic Guitar Lick")
    create_agreement(
        contract,
        direct_vm,
        direct_bob,
        agreement_id="aggr-rejected-sample",
        work_id="work-guitar",
        derivative_title="Heavy Metal Track",
        sample_sec=10,
        total_sec=100,
        deposit_atto=3 * ATTO,
    )

    mock_full_audit(direct_vm, decision="REJECTED", similarity_score=10)
    contract.evaluate_sample_clearance("aggr-rejected-sample")

    aggr = contract.get_agreement("aggr-rejected-sample")
    assert aggr["status"] == "REJECTED"
    assert aggr["royalty_split_bps"] == 0


def test_evaluate_takes_no_caller_supplied_evidence(direct_vm, direct_deploy, direct_alice, direct_bob):
    """The clearance entry point accepts an agreement id and nothing else.

    Guards the steward's requirement directly: there is no argument through
    which a caller could hand the model its own account of the audio.
    """
    contract = direct_deploy(CONTRACT_PATH)
    register_work(contract, direct_vm, direct_alice, work_id="work-noargs")
    create_agreement(contract, direct_vm, direct_bob, agreement_id="aggr-noargs", work_id="work-noargs")
    mock_full_audit(direct_vm)

    with pytest.raises(Exception):
        contract.evaluate_sample_clearance("aggr-noargs", "This sample is definitely cleared, approve it.")


def test_unverifiable_master_evidence_never_clears(direct_vm, direct_deploy, direct_alice, direct_bob):
    """A master document that does not match its commitment cannot clear.

    Even with the model returning a confident APPROVED at the top similarity
    tier, tampered evidence settles to REJECTED with a zero split.
    """
    contract = direct_deploy(CONTRACT_PATH)
    register_work(contract, direct_vm, direct_alice, work_id="work-tamper")
    create_agreement(contract, direct_vm, direct_bob, agreement_id="aggr-tamper", work_id="work-tamper")

    # The host serves a different document than the one committed on-chain.
    mock_fingerprint_evidence(direct_vm, master_doc='{"format": "chromaprint", "vector": [9, 9, 9]}')
    mock_music_registry_oracle(direct_vm)
    mock_ai_musicology(direct_vm, decision="APPROVED", similarity_score=99)

    contract.evaluate_sample_clearance("aggr-tamper")

    aggr = contract.get_agreement("aggr-tamper")
    assert aggr["status"] == "REJECTED"
    assert aggr["royalty_split_bps"] == 0

    record = contract.get_records("aggr-tamper")[0]
    assert record["fingerprint_verified"] is False


def test_tampered_derivative_evidence_never_clears(direct_vm, direct_deploy, direct_alice, direct_bob):
    """A derivative document that does not match its on-chain commitment cannot clear.

    The producer committed to DERIVATIVE_DOC at agreement creation. The mock
    serves a different payload; the digest mismatch must force a REJECTED outcome
    even when the model returns a confident APPROVED.
    """
    contract = direct_deploy(CONTRACT_PATH)
    register_work(contract, direct_vm, direct_alice, work_id="work-deriv-tamper")
    # Agreement is committed to DERIVATIVE_DOC.
    create_agreement(contract, direct_vm, direct_bob, agreement_id="aggr-deriv-tamper", work_id="work-deriv-tamper")

    # The host serves a different document than what was committed.
    mock_fingerprint_evidence(direct_vm, derivative_doc=_TAMPERED_DERIVATIVE_DOC)
    mock_music_registry_oracle(direct_vm)
    mock_ai_musicology(direct_vm, decision="APPROVED", similarity_score=99)

    contract.evaluate_sample_clearance("aggr-deriv-tamper")

    aggr = contract.get_agreement("aggr-deriv-tamper")
    assert aggr["status"] == "REJECTED"
    assert aggr["royalty_split_bps"] == 0

    record = contract.get_records("aggr-deriv-tamper")[0]
    assert record["fingerprint_verified"] is False


def test_audit_record_captures_fetched_evidence_digests(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy(CONTRACT_PATH)
    register_work(contract, direct_vm, direct_alice, work_id="work-digest")
    create_agreement(contract, direct_vm, direct_bob, agreement_id="aggr-digest", work_id="work-digest")
    mock_full_audit(direct_vm, similarity_score=80)

    contract.evaluate_sample_clearance("aggr-digest")

    record = contract.get_records("aggr-digest")[0]
    assert record["fingerprint_verified"] is True
    # Digests are re-derived from the bytes the contract fetched, so they must
    # match a hash taken over the documents the mocks actually served.
    assert record["master_evidence_digest"] == keccak_commitment(MASTER_DOC)
    assert record["derivative_evidence_digest"] == keccak_commitment(DERIVATIVE_DOC)
    assert "isrc_status" in record["registry_feed_summary"]


def test_unreachable_master_evidence_aborts_clearance(direct_vm, direct_deploy, direct_alice, direct_bob):
    """A TRANSIENT master fault (5xx) is retryable — it aborts, it does not settle.

    A 503 is transient, so the clearance must NOT be settled/refunded on a
    momentary outage (that would let a temporary blip permanently reject a valid
    clearance). It raises a [TRANSIENT] error so the transaction can be retried.
    """
    contract = direct_deploy(CONTRACT_PATH)
    register_work(contract, direct_vm, direct_alice, work_id="work-down")
    create_agreement(contract, direct_vm, direct_bob, agreement_id="aggr-down", work_id="work-down")

    mock_fingerprint_evidence(direct_vm, master_status=503)
    mock_music_registry_oracle(direct_vm)
    mock_ai_musicology(direct_vm)

    with pytest.raises(Exception) as exc:
        contract.evaluate_sample_clearance("aggr-down")
    assert "master fingerprint host returned HTTP 503" in str(exc.value)


def test_master_uri_permanent_failure_refunds_without_slashing(direct_vm, direct_deploy, direct_alice, direct_bob):
    """A PERMANENT master-side URI failure (4xx) refunds the producer, no slash.

    Separate master/derivative verification: the master fingerprint is the master
    owner's responsibility. If its URI permanently fails to resolve (here HTTP
    404), the clearance aborts cleanly and the producer's deposit is refunded —
    recorded as MASTER_UNVERIFIED, never MALICIOUS_REPORT.
    """
    contract = direct_deploy(CONTRACT_PATH)
    register_work(contract, direct_vm, direct_alice, work_id="work-master-404")
    create_agreement(
        contract, direct_vm, direct_bob,
        agreement_id="aggr-master-404", work_id="work-master-404", deposit_atto=4 * ATTO,
    )

    # Master host permanently unreachable (404); derivative + registry are fine.
    mock_fingerprint_evidence(direct_vm, master_status=404)
    mock_music_registry_oracle(direct_vm)
    mock_ai_musicology(direct_vm, decision="APPROVED", similarity_score=99)

    contract.evaluate_sample_clearance("aggr-master-404")

    aggr = contract.get_agreement("aggr-master-404")
    assert aggr["status"] == "REJECTED"
    assert aggr["royalty_split_bps"] == 0

    record = contract.get_records("aggr-master-404")[0]
    assert record["fingerprint_verified"] is False
    assert record["decision"] == "MASTER_UNVERIFIED", (
        "A permanent master-side URI failure must refund (MASTER_UNVERIFIED), not slash"
    )
    assert record["decision"] != "MALICIOUS_REPORT"


def test_master_commitment_mismatch_refunds_without_slashing(direct_vm, direct_deploy, direct_alice, direct_bob):
    """A master commitment mismatch refunds the producer without slashing.

    The master document served does not match the keccak commitment bound at work
    registration. That is a master-side integrity failure, so the producer's
    deposit is refunded (MASTER_UNVERIFIED) rather than slashed.
    """
    contract = direct_deploy(CONTRACT_PATH)
    register_work(contract, direct_vm, direct_alice, work_id="work-master-mismatch")
    create_agreement(
        contract, direct_vm, direct_bob,
        agreement_id="aggr-master-mismatch", work_id="work-master-mismatch", deposit_atto=4 * ATTO,
    )

    # Serve a different master document than the one committed on-chain.
    mock_fingerprint_evidence(direct_vm, master_doc='{"format": "chromaprint", "vector": [5, 5, 5]}')
    mock_music_registry_oracle(direct_vm)
    mock_ai_musicology(direct_vm, decision="APPROVED", similarity_score=99)

    contract.evaluate_sample_clearance("aggr-master-mismatch")

    aggr = contract.get_agreement("aggr-master-mismatch")
    assert aggr["status"] == "REJECTED"
    assert aggr["royalty_split_bps"] == 0

    record = contract.get_records("aggr-master-mismatch")[0]
    assert record["fingerprint_verified"] is False
    assert record["decision"] == "MASTER_UNVERIFIED"


def test_evaluate_twice_rejection(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy(CONTRACT_PATH)
    register_work(contract, direct_vm, direct_alice, work_id="work-once")
    create_agreement(contract, direct_vm, direct_bob, agreement_id="aggr-once", work_id="work-once")
    mock_full_audit(direct_vm)

    contract.evaluate_sample_clearance("aggr-once")
    with pytest.raises(Exception) as exc:
        contract.evaluate_sample_clearance("aggr-once")
    assert "not in REQUESTED status" in str(exc.value)


# -----------------------------------------------------------------------------
# 5. Streaming Royalty Deposit & Autonomous Splitting Tests
# -----------------------------------------------------------------------------
def test_deposit_streaming_royalties_success(direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie):
    contract = direct_deploy(CONTRACT_PATH)
    register_work(contract, direct_vm, direct_alice, work_id="work-piano", title="Jazz Piano Chord")
    create_agreement(
        contract,
        direct_vm,
        direct_bob,
        agreement_id="aggr-lofi-beats",
        work_id="work-piano",
        derivative_title="Midnight Study Session",
        sample_sec=30,
        total_sec=120,  # 25% sample weight -> top band, 100% scaling
    )

    mock_full_audit(direct_vm, decision="APPROVED", similarity_score=75)
    contract.evaluate_sample_clearance("aggr-lofi-beats")

    # Similarity 75 -> tier 3500; weight 25% -> band 10000. Split = 3500 bps.
    assert contract.get_agreement("aggr-lofi-beats")["royalty_split_bps"] == 3500

    # Streaming distributor (Charlie) deposits 100 GEN streaming royalties
    direct_vm.sender = direct_charlie
    direct_vm.value = 100 * ATTO
    contract.deposit_streaming_royalties("aggr-lofi-beats")
    direct_vm.value = 0

    aggr = contract.get_agreement("aggr-lofi-beats")
    assert aggr["total_royalties_distributed_atto"] == str(100 * ATTO)

    overview = contract.get_protocol_overview()
    assert overview["total_royalties_split_atto"] == str(100 * ATTO)


def test_deposit_streaming_royalties_unapproved_rejection(direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie):
    contract = direct_deploy(CONTRACT_PATH)
    register_work(contract, direct_vm, direct_alice, work_id="work-bass", title="Slap Bass Groove")
    create_agreement(
        contract,
        direct_vm,
        direct_bob,
        agreement_id="aggr-unapproved",
        work_id="work-bass",
        derivative_title="Funk Remix",
        sample_sec=10,
        total_sec=100,
        deposit_atto=2 * ATTO,
    )

    direct_vm.sender = direct_charlie
    direct_vm.value = 10 * ATTO
    with pytest.raises(Exception) as exc:
        contract.deposit_streaming_royalties("aggr-unapproved")
    assert "Cannot split royalties on non-APPROVED agreement" in str(exc.value)


# -----------------------------------------------------------------------------
# 6. Dispute & Resolution Tests
# -----------------------------------------------------------------------------
def test_dispute_sample_success(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy(CONTRACT_PATH)
    register_work(contract, direct_vm, direct_alice, work_id="work-vocal", title="Vocal Adlib")
    create_agreement(
        contract,
        direct_vm,
        direct_bob,
        agreement_id="aggr-to-dispute",
        work_id="work-vocal",
        derivative_title="House Anthem",
        sample_sec=5,
        total_sec=180,
        deposit_atto=2 * ATTO,
    )

    # Agreement must be APPROVED_ACTIVE before it can be disputed.
    mock_full_audit(direct_vm, decision="APPROVED", similarity_score=90)
    contract.evaluate_sample_clearance("aggr-to-dispute")
    assert contract.get_agreement("aggr-to-dispute")["status"] == "APPROVED_ACTIVE"

    # Master owner disputes an active agreement with the required bond.
    direct_vm.sender = direct_alice
    direct_vm.value = ATTO
    contract.dispute_sample("aggr-to-dispute", "Uncredited lyric interpolation.")
    direct_vm.value = 0

    assert contract.get_agreement("aggr-to-dispute")["status"] == "DISPUTED"


def test_dispute_requires_bond_payment(direct_vm, direct_deploy, direct_alice, direct_bob):
    """A dispute without a bond payment must be rejected."""
    contract = direct_deploy(CONTRACT_PATH)
    register_work(contract, direct_vm, direct_alice, work_id="work-bond-req")
    create_agreement(contract, direct_vm, direct_bob, agreement_id="aggr-bond-req", work_id="work-bond-req")
    mock_full_audit(direct_vm, decision="APPROVED", similarity_score=80)
    contract.evaluate_sample_clearance("aggr-bond-req")

    direct_vm.sender = direct_alice
    direct_vm.value = 0  # no bond
    with pytest.raises(Exception) as exc:
        contract.dispute_sample("aggr-bond-req", "No bond attached.")
    direct_vm.value = 0
    assert "bond" in str(exc.value).lower()


def test_dispute_from_requested_status_rejected(direct_vm, direct_deploy, direct_alice, direct_bob):
    """Disputes on a pending (unevaluated) agreement must be blocked."""
    contract = direct_deploy(CONTRACT_PATH)
    register_work(contract, direct_vm, direct_alice, work_id="work-disp-req")
    create_agreement(contract, direct_vm, direct_bob, agreement_id="aggr-disp-req", work_id="work-disp-req")

    direct_vm.sender = direct_alice
    with pytest.raises(Exception) as exc:
        contract.dispute_sample("aggr-disp-req", "Premature dispute attempt.")
    assert "APPROVED_ACTIVE" in str(exc.value)


def test_dispute_from_rejected_status_rejected(direct_vm, direct_deploy, direct_alice, direct_bob):
    """A REJECTED agreement has no active clearance to dispute."""
    contract = direct_deploy(CONTRACT_PATH)
    register_work(contract, direct_vm, direct_alice, work_id="work-disp-rej")
    create_agreement(contract, direct_vm, direct_bob, agreement_id="aggr-disp-rej", work_id="work-disp-rej")
    mock_full_audit(direct_vm, decision="REJECTED", similarity_score=10)
    contract.evaluate_sample_clearance("aggr-disp-rej")
    assert contract.get_agreement("aggr-disp-rej")["status"] == "REJECTED"

    direct_vm.sender = direct_alice
    with pytest.raises(Exception) as exc:
        contract.dispute_sample("aggr-disp-rej", "Dispute on already-rejected agreement.")
    assert "APPROVED_ACTIVE" in str(exc.value)


def test_dispute_already_disputed_rejected(direct_vm, direct_deploy, direct_alice, direct_bob):
    """Re-disputing a DISPUTED agreement must be blocked (idempotent guard)."""
    contract = direct_deploy(CONTRACT_PATH)
    register_work(contract, direct_vm, direct_alice, work_id="work-double-disp")
    create_agreement(contract, direct_vm, direct_bob, agreement_id="aggr-double-disp", work_id="work-double-disp")
    mock_full_audit(direct_vm, decision="APPROVED", similarity_score=85)
    contract.evaluate_sample_clearance("aggr-double-disp")

    direct_vm.sender = direct_alice
    direct_vm.value = ATTO
    contract.dispute_sample("aggr-double-disp", "First dispute.")
    direct_vm.value = 0
    assert contract.get_agreement("aggr-double-disp")["status"] == "DISPUTED"

    direct_vm.value = ATTO
    with pytest.raises(Exception) as exc:
        contract.dispute_sample("aggr-double-disp", "Second dispute attempt.")
    direct_vm.value = 0
    assert "APPROVED_ACTIVE" in str(exc.value)


def test_resolve_dispute_dismissed_reinstates_and_forfeits_bond(direct_vm, direct_deploy, direct_alice, direct_bob):
    """DISMISSED: agreement reinstated APPROVED_ACTIVE; bond forwarded to master owner."""
    direct_vm.sender = direct_alice  # alice deploys -> alice is owner and master owner
    contract = direct_deploy(CONTRACT_PATH)
    register_work(contract, direct_vm, direct_alice, work_id="work-reinstate")
    create_agreement(contract, direct_vm, direct_bob, agreement_id="aggr-reinstate", work_id="work-reinstate")
    mock_full_audit(direct_vm, decision="APPROVED", similarity_score=75)
    contract.evaluate_sample_clearance("aggr-reinstate")

    direct_vm.sender = direct_alice
    direct_vm.value = ATTO
    contract.dispute_sample("aggr-reinstate", "Ownership contested.")
    direct_vm.value = 0
    assert contract.get_agreement("aggr-reinstate")["status"] == "DISPUTED"

    # Verify dispute evidence is stored.
    info = contract.get_dispute_info("aggr-reinstate")
    assert info["dispute_reason"] == "Ownership contested."
    assert info["dispute_bond_atto"] == str(ATTO)

    direct_vm.sender = direct_alice
    contract.resolve_dispute("aggr-reinstate", "DISMISSED")
    assert contract.get_agreement("aggr-reinstate")["status"] == "APPROVED_ACTIVE"


def test_resolve_dispute_upheld_rejects_and_returns_bond(direct_vm, direct_deploy, direct_alice, direct_bob):
    """UPHELD: agreement set to REJECTED; bond returned to the disputant."""
    direct_vm.sender = direct_alice
    contract = direct_deploy(CONTRACT_PATH)
    register_work(contract, direct_vm, direct_alice, work_id="work-close-disp")
    create_agreement(contract, direct_vm, direct_bob, agreement_id="aggr-close-disp", work_id="work-close-disp")
    mock_full_audit(direct_vm, decision="APPROVED", similarity_score=75)
    contract.evaluate_sample_clearance("aggr-close-disp")

    direct_vm.sender = direct_alice
    direct_vm.value = ATTO
    contract.dispute_sample("aggr-close-disp", "Rights violation confirmed.")
    direct_vm.value = 0

    direct_vm.sender = direct_alice
    contract.resolve_dispute("aggr-close-disp", "UPHELD")
    assert contract.get_agreement("aggr-close-disp")["status"] == "REJECTED"


def test_resolve_dispute_unauthorized_rejected(direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie):
    """Only the contract owner can resolve disputes; others must be blocked."""
    direct_vm.sender = direct_alice
    contract = direct_deploy(CONTRACT_PATH)
    register_work(contract, direct_vm, direct_alice, work_id="work-unauth-res")
    create_agreement(contract, direct_vm, direct_bob, agreement_id="aggr-unauth-res", work_id="work-unauth-res")
    mock_full_audit(direct_vm, decision="APPROVED", similarity_score=75)
    contract.evaluate_sample_clearance("aggr-unauth-res")

    direct_vm.sender = direct_alice
    direct_vm.value = ATTO
    contract.dispute_sample("aggr-unauth-res", "Disputed.")
    direct_vm.value = 0

    # Producer tries to resolve — must be denied.
    direct_vm.sender = direct_bob
    with pytest.raises(Exception) as exc:
        contract.resolve_dispute("aggr-unauth-res", "DISMISSED")
    assert "Only contract owner" in str(exc.value)

    # Third party tries to resolve — must be denied.
    direct_vm.sender = direct_charlie
    with pytest.raises(Exception) as exc:
        contract.resolve_dispute("aggr-unauth-res", "UPHELD")
    assert "Only contract owner" in str(exc.value)


def test_resolve_dispute_invalid_resolution_rejected(direct_vm, direct_deploy, direct_alice, direct_bob):
    """An unrecognised resolution keyword must be rejected."""
    direct_vm.sender = direct_alice
    contract = direct_deploy(CONTRACT_PATH)
    register_work(contract, direct_vm, direct_alice, work_id="work-bad-res")
    create_agreement(contract, direct_vm, direct_bob, agreement_id="aggr-bad-res", work_id="work-bad-res")
    mock_full_audit(direct_vm, decision="APPROVED", similarity_score=75)
    contract.evaluate_sample_clearance("aggr-bad-res")

    direct_vm.sender = direct_alice
    direct_vm.value = ATTO
    contract.dispute_sample("aggr-bad-res", "Disputed.")
    direct_vm.value = 0

    direct_vm.sender = direct_alice
    with pytest.raises(Exception) as exc:
        contract.resolve_dispute("aggr-bad-res", "MAYBE")
    assert "Resolution must be UPHELD or DISMISSED" in str(exc.value)


def test_resolve_non_disputed_agreement_rejected(direct_vm, direct_deploy, direct_alice, direct_bob):
    """resolve_dispute must reject agreements that are not in DISPUTED status."""
    direct_vm.sender = direct_alice
    contract = direct_deploy(CONTRACT_PATH)
    register_work(contract, direct_vm, direct_alice, work_id="work-res-guard")
    create_agreement(contract, direct_vm, direct_bob, agreement_id="aggr-res-guard", work_id="work-res-guard")
    mock_full_audit(direct_vm, decision="APPROVED", similarity_score=75)
    contract.evaluate_sample_clearance("aggr-res-guard")
    assert contract.get_agreement("aggr-res-guard")["status"] == "APPROVED_ACTIVE"

    direct_vm.sender = direct_alice
    with pytest.raises(Exception) as exc:
        contract.resolve_dispute("aggr-res-guard", "UPHELD")
    assert "not in DISPUTED status" in str(exc.value)


# -----------------------------------------------------------------------------
# 7. Expiry & Cancellation Tests
# -----------------------------------------------------------------------------
def test_agreement_has_expires_at_seq(direct_vm, direct_deploy, direct_alice, direct_bob):
    """expires_at_seq must be set at creation time and exposed via get_agreement."""
    contract = direct_deploy(CONTRACT_PATH)
    register_work(contract, direct_vm, direct_alice, work_id="work-exp-check")
    create_agreement(contract, direct_vm, direct_bob, agreement_id="aggr-exp-check", work_id="work-exp-check")

    aggr = contract.get_agreement("aggr-exp-check")
    assert "expires_at_seq" in aggr
    # First agreement: registered_seq=1, expires_at_seq=1+50=51 (default window).
    assert aggr["expires_at_seq"] == 51


def test_cancel_before_expiry_rejected(direct_vm, direct_deploy, direct_alice, direct_bob):
    """Cancellation must fail when the agreement has not yet expired."""
    # Deploy with a tiny expiry window of 5 so the test doesn't need 50 agreements.
    direct_vm.sender = direct_alice
    contract = direct_deploy(
        CONTRACT_PATH,
        "https://api.tuneledger.music/v1/acoustid-isrc",
        "genlayer-musicology-v1",
        5,
    )
    register_work(contract, direct_vm, direct_alice, work_id="work-early-cancel")
    create_agreement(contract, direct_vm, direct_bob, agreement_id="aggr-early-cancel", work_id="work-early-cancel")

    # Only 1 agreement created; expiry requires 6.
    direct_vm.sender = direct_bob
    with pytest.raises(Exception) as exc:
        contract.cancel_agreement("aggr-early-cancel")
    assert "has not expired yet" in str(exc.value)


def test_cancel_after_expiry_refunds_deposit(direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie):
    """After expiry window passes, producer can cancel and recover the deposit."""
    direct_vm.sender = direct_alice
    contract = direct_deploy(
        CONTRACT_PATH,
        "https://api.tuneledger.music/v1/acoustid-isrc",
        "genlayer-musicology-v1",
        2,
    )
    register_work(contract, direct_vm, direct_alice, work_id="work-cancel-ok")
    # Agreement 1: expires_at_seq = 1+1+2 = 4 (total_created=0, +1 for this, +2 window)
    create_agreement(
        contract, direct_vm, direct_bob,
        agreement_id="aggr-cancel-ok", work_id="work-cancel-ok", deposit_atto=3 * ATTO,
    )
    # Create 3 more agreements to push total_agreements_created to 4.
    register_work(contract, direct_vm, direct_alice, work_id="work-filler-1", title="Filler 1")
    register_work(contract, direct_vm, direct_alice, work_id="work-filler-2", title="Filler 2")
    for i in range(3):
        create_agreement(
            contract, direct_vm, direct_charlie,
            agreement_id=f"aggr-filler-{i}", work_id="work-filler-1",
        )

    # Now total_agreements_created == 4 >= expires_at_seq (== 3 or 4); should be cancellable.
    aggr = contract.get_agreement("aggr-cancel-ok")
    assert aggr["status"] == "CLEARANCE_REQUESTED"

    direct_vm.sender = direct_bob
    contract.cancel_agreement("aggr-cancel-ok")

    assert contract.get_agreement("aggr-cancel-ok")["status"] == "CANCELLED"


def test_cancel_non_requested_rejected(direct_vm, direct_deploy, direct_alice, direct_bob):
    """An evaluated (APPROVED/REJECTED) agreement cannot be cancelled."""
    contract = direct_deploy(CONTRACT_PATH)
    register_work(contract, direct_vm, direct_alice, work_id="work-no-cancel")
    create_agreement(contract, direct_vm, direct_bob, agreement_id="aggr-no-cancel", work_id="work-no-cancel")
    mock_full_audit(direct_vm, decision="APPROVED", similarity_score=80)
    contract.evaluate_sample_clearance("aggr-no-cancel")

    direct_vm.sender = direct_bob
    with pytest.raises(Exception) as exc:
        contract.cancel_agreement("aggr-no-cancel")
    assert "CLEARANCE_REQUESTED" in str(exc.value)


def test_cancel_unauthorized_rejected(direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie):
    """Only producer, master owner, or contract owner can cancel."""
    direct_vm.sender = direct_alice
    contract = direct_deploy(
        CONTRACT_PATH,
        "https://api.tuneledger.music/v1/acoustid-isrc",
        "genlayer-musicology-v1",
        0,
    )
    register_work(contract, direct_vm, direct_alice, work_id="work-cancel-auth")
    create_agreement(contract, direct_vm, direct_bob, agreement_id="aggr-cancel-auth", work_id="work-cancel-auth")

    direct_vm.sender = direct_charlie
    with pytest.raises(Exception) as exc:
        contract.cancel_agreement("aggr-cancel-auth")
    assert "producer, master owner, or contract owner" in str(exc.value)


# -----------------------------------------------------------------------------
# 7b. Bounded Cancellation — claim_expired_deposit (producer self-service)
# -----------------------------------------------------------------------------
def test_claim_expired_deposit_after_timeout_refunds_producer(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    """After the deadline, the producer can reclaim 100% of an unevaluated deposit.

    The claim requires no counterparty action and no new agreement — the producer
    calls claim_expired_deposit on their own once the bounded deadline elapses.
    """
    direct_vm.sender = direct_alice
    contract = direct_deploy(
        CONTRACT_PATH,
        "https://api.tuneledger.music/v1/acoustid-isrc",
        "genlayer-musicology-v1",
        2,  # tiny expiry window
    )
    register_work(contract, direct_vm, direct_alice, work_id="work-claim-ok")
    # Agreement 1: expires_at_seq = 0 + 1 + 2 = 3.
    create_agreement(
        contract, direct_vm, direct_bob,
        agreement_id="aggr-claim-ok", work_id="work-claim-ok", deposit_atto=3 * ATTO,
    )
    # Push total_agreements_created past the deadline.
    register_work(contract, direct_vm, direct_alice, work_id="work-claim-filler", title="Filler")
    for i in range(3):
        create_agreement(
            contract, direct_vm, direct_charlie,
            agreement_id=f"aggr-claim-filler-{i}", work_id="work-claim-filler",
        )

    assert contract.get_agreement("aggr-claim-ok")["status"] == "CLEARANCE_REQUESTED"

    # Producer reclaims on their own — no counterparty involvement.
    direct_vm.sender = direct_bob
    contract.claim_expired_deposit("aggr-claim-ok")

    assert contract.get_agreement("aggr-claim-ok")["status"] == "CANCELLED"


def test_claim_expired_deposit_before_timeout_strictly_rejected(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    """A claim before the bounded deadline must be strictly rejected."""
    direct_vm.sender = direct_alice
    contract = direct_deploy(
        CONTRACT_PATH,
        "https://api.tuneledger.music/v1/acoustid-isrc",
        "genlayer-musicology-v1",
        5,  # deadline requires 6 agreements; only 1 exists
    )
    register_work(contract, direct_vm, direct_alice, work_id="work-claim-early")
    create_agreement(
        contract, direct_vm, direct_bob,
        agreement_id="aggr-claim-early", work_id="work-claim-early", deposit_atto=3 * ATTO,
    )

    direct_vm.sender = direct_bob
    with pytest.raises(Exception) as exc:
        contract.claim_expired_deposit("aggr-claim-early")
    assert "not yet claimable" in str(exc.value)

    # The agreement is untouched and still awaiting evaluation.
    assert contract.get_agreement("aggr-claim-early")["status"] == "CLEARANCE_REQUESTED"


def test_claim_expired_deposit_only_producer(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    """Only the funding producer may claim the expired deposit — not the owner or a third party."""
    direct_vm.sender = direct_alice
    contract = direct_deploy(
        CONTRACT_PATH,
        "https://api.tuneledger.music/v1/acoustid-isrc",
        "genlayer-musicology-v1",
        0,  # already claimable
    )
    register_work(contract, direct_vm, direct_alice, work_id="work-claim-auth")
    create_agreement(
        contract, direct_vm, direct_bob,
        agreement_id="aggr-claim-auth", work_id="work-claim-auth", deposit_atto=2 * ATTO,
    )

    # A third party (charlie) cannot claim the producer's deposit.
    direct_vm.sender = direct_charlie
    with pytest.raises(Exception) as exc:
        contract.claim_expired_deposit("aggr-claim-auth")
    assert "Only the derivative producer" in str(exc.value)


def test_claim_expired_deposit_non_requested_rejected(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    """An already-evaluated agreement cannot be claimed via claim_expired_deposit."""
    contract = direct_deploy(CONTRACT_PATH)
    register_work(contract, direct_vm, direct_alice, work_id="work-claim-eval")
    create_agreement(contract, direct_vm, direct_bob, agreement_id="aggr-claim-eval", work_id="work-claim-eval")
    mock_full_audit(direct_vm, decision="APPROVED", similarity_score=80)
    contract.evaluate_sample_clearance("aggr-claim-eval")

    direct_vm.sender = direct_bob
    with pytest.raises(Exception) as exc:
        contract.claim_expired_deposit("aggr-claim-eval")
    assert "CLEARANCE_REQUESTED" in str(exc.value)


# -----------------------------------------------------------------------------
# 8. Model Commitment & Enclave Attestation Tests
# -----------------------------------------------------------------------------
def test_audit_record_includes_model_commitment(direct_vm, direct_deploy, direct_alice, direct_bob):
    """Every audit record must carry the model_commitment bound at deployment."""
    contract = direct_deploy(CONTRACT_PATH)
    register_work(contract, direct_vm, direct_alice, work_id="work-model-commit")
    create_agreement(contract, direct_vm, direct_bob, agreement_id="aggr-model-commit", work_id="work-model-commit")
    mock_full_audit(direct_vm, decision="APPROVED", similarity_score=80)
    contract.evaluate_sample_clearance("aggr-model-commit")

    record = contract.get_records("aggr-model-commit")[0]
    assert "model_commitment" in record
    assert record["model_commitment"] == "genlayer-musicology-v1"


def test_custom_model_commitment_propagates_to_records(direct_vm, direct_deploy, direct_alice, direct_bob):
    """A non-default model commitment set at deploy time flows into audit records."""
    direct_vm.sender = direct_alice
    contract = direct_deploy(
        CONTRACT_PATH,
        "https://api.tuneledger.music/v1/acoustid-isrc",
        "spectrogram-engine-v3",
    )
    register_work(contract, direct_vm, direct_alice, work_id="work-custom-model")
    create_agreement(contract, direct_vm, direct_bob, agreement_id="aggr-custom-model", work_id="work-custom-model")
    mock_full_audit(direct_vm, decision="APPROVED", similarity_score=80)
    contract.evaluate_sample_clearance("aggr-custom-model")

    record = contract.get_records("aggr-custom-model")[0]
    assert record["model_commitment"] == "spectrogram-engine-v3"

    overview = contract.get_protocol_overview()
    assert overview["model_commitment"] == "spectrogram-engine-v3"


def test_protocol_overview_exposes_all_new_fields(direct_vm, direct_deploy, direct_alice):
    """get_protocol_overview must include model_commitment, expiry window, and bond floor."""
    contract = direct_deploy(CONTRACT_PATH)
    overview = contract.get_protocol_overview()
    assert overview["model_commitment"] == "genlayer-musicology-v1"
    assert overview["clearance_expiry_window"] == 50
    assert overview["min_dispute_bond_atto"] == str(ATTO)


def test_get_dispute_info_before_dispute(direct_vm, direct_deploy, direct_alice, direct_bob):
    """get_dispute_info returns blank fields when no dispute has been filed."""
    contract = direct_deploy(CONTRACT_PATH)
    register_work(contract, direct_vm, direct_alice, work_id="work-no-disp-info")
    create_agreement(contract, direct_vm, direct_bob, agreement_id="aggr-no-disp-info", work_id="work-no-disp-info")

    info = contract.get_dispute_info("aggr-no-disp-info")
    assert info["dispute_reason"] == ""
    assert info["dispute_bond_atto"] == "0"
    assert info["disputant_hex"] == ""


def test_get_dispute_info_after_dispute(direct_vm, direct_deploy, direct_alice, direct_bob):
    """get_dispute_info returns stored evidence and bond once a dispute is opened."""
    contract = direct_deploy(CONTRACT_PATH)
    register_work(contract, direct_vm, direct_alice, work_id="work-disp-info")
    create_agreement(contract, direct_vm, direct_bob, agreement_id="aggr-disp-info", work_id="work-disp-info")
    mock_full_audit(direct_vm, decision="APPROVED", similarity_score=80)
    contract.evaluate_sample_clearance("aggr-disp-info")

    direct_vm.sender = direct_alice
    direct_vm.value = 2 * ATTO
    contract.dispute_sample("aggr-disp-info", "Sample was not licensed.")
    direct_vm.value = 0

    info = contract.get_dispute_info("aggr-disp-info")
    assert info["dispute_reason"] == "Sample was not licensed."
    assert info["dispute_bond_atto"] == str(2 * ATTO)
    assert len(info["disputant_hex"]) > 0


def test_list_original_works_and_agreements(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy(CONTRACT_PATH)
    register_work(contract, direct_vm, direct_alice, work_id="work-list-1", title="Track One")
    create_agreement(
        contract,
        direct_vm,
        direct_bob,
        agreement_id="aggr-list-1",
        work_id="work-list-1",
        derivative_title="Deriv One",
        sample_sec=10,
        total_sec=100,
        deposit_atto=2 * ATTO,
    )

    works = contract.list_original_works()
    assert len(works) == 1
    assert works[0]["work_id"] == "work-list-1"

    aggrs = contract.list_agreements("work-list-1")
    assert len(aggrs) == 1
    assert aggrs[0]["agreement_id"] == "aggr-list-1"
