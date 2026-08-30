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
    """Fingerprint evidence is mandatory; a dead host stops the clearance."""
    contract = direct_deploy(CONTRACT_PATH)
    register_work(contract, direct_vm, direct_alice, work_id="work-down")
    create_agreement(contract, direct_vm, direct_bob, agreement_id="aggr-down", work_id="work-down")

    mock_fingerprint_evidence(direct_vm, master_status=503)
    mock_music_registry_oracle(direct_vm)
    mock_ai_musicology(direct_vm)

    with pytest.raises(Exception) as exc:
        contract.evaluate_sample_clearance("aggr-down")
    assert "master fingerprint host returned HTTP 503" in str(exc.value)


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
# 6. Dispute & Listing Tests
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

    # Master owner disputes sample
    direct_vm.sender = direct_alice
    contract.dispute_sample("aggr-to-dispute", "Uncredited lyric interpolation.")

    assert contract.get_agreement("aggr-to-dispute")["status"] == "DISPUTED"


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
