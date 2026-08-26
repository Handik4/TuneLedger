"""Comprehensive Direct Pytest Suite for TuneLedger Royalty Escrow Protocol."""

import pytest
from conftest import (
    CONTRACT_PATH,
    mock_ai_musicology,
    mock_music_registry_oracle,
)

ATTO = 10**18


# -----------------------------------------------------------------------------
# 1. Protocol Overview & Initialization
# -----------------------------------------------------------------------------
def test_initial_protocol_overview(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT_PATH)
    overview = contract.get_protocol_overview()
    assert overview["total_works_registered"] == 0
    assert overview["total_agreements_created"] == 0
    assert overview["total_royalties_split_atto"] == "0"


# -----------------------------------------------------------------------------
# 2. Master Work Registration Tests
# -----------------------------------------------------------------------------
def test_register_original_work_success(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = direct_alice

    contract.register_original_work(
        "work-amen-break",
        "Amen, Brother",
        "US-S1Z-69-00001",
        "sha256:6-second-drum-break-solo-g-c-coleman",
    )

    work = contract.get_original_work("work-amen-break")
    assert work["work_id"] == "work-amen-break"
    assert work["title"] == "Amen, Brother"
    assert work["isrc_code"] == "US-S1Z-69-00001"
    assert work["master_owner"].lower().removeprefix("0x") == direct_alice.hex().lower()


def test_register_original_work_empty_fields_rejection(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = direct_alice

    with pytest.raises(Exception) as exc:
        contract.register_original_work(
            "",
            "Title",
            "ISRC",
            "Hash",
        )
    assert "Work ID cannot be empty" in str(exc.value)


def test_register_duplicate_work_rejection(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = direct_alice

    contract.register_original_work(
        "work-dup",
        "Track 1",
        "ISRC-1",
        "Hash-1",
    )

    with pytest.raises(Exception) as exc:
        contract.register_original_work(
            "work-dup",
            "Track 2",
            "ISRC-2",
            "Hash-2",
        )
    assert "already registered" in str(exc.value)


# -----------------------------------------------------------------------------
# 3. Clearance Agreement Request Tests
# -----------------------------------------------------------------------------
def test_create_clearance_agreement_success(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy(CONTRACT_PATH)

    # Alice registers original master
    direct_vm.sender = direct_alice
    contract.register_original_work(
        "work-funk-riff",
        "Funky Drummer",
        "US-JBR-70-00101",
        "sha256:clyde-stubblefield-break",
    )

    # Bob requests sample clearance for 15s in a 180s track with 2 GEN deposit
    direct_vm.sender = direct_bob
    direct_vm.value = 2 * ATTO
    contract.create_clearance_agreement(
        "aggr-hiphop-beat-01",
        "work-funk-riff",
        "Straight Outta Rhythm",
        15,
        180,
    )

    aggr = contract.get_agreement("aggr-hiphop-beat-01")
    assert aggr["agreement_id"] == "aggr-hiphop-beat-01"
    assert aggr["original_work_id"] == "work-funk-riff"
    assert aggr["derivative_title"] == "Straight Outta Rhythm"
    assert aggr["sample_duration_sec"] == 15
    assert aggr["total_track_sec"] == 180
    assert aggr["clearance_deposit_atto"] == str(2 * ATTO)
    assert aggr["status"] == "CLEARANCE_REQUESTED"


def test_create_clearance_agreement_invalid_durations_rejection(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = direct_alice
    contract.register_original_work(
        "work-riff",
        "Title",
        "ISRC",
        "Hash",
    )

    direct_vm.sender = direct_bob
    direct_vm.value = 2 * ATTO
    with pytest.raises(Exception) as exc:
        contract.create_clearance_agreement(
            "aggr-bad-duration",
            "work-riff",
            "Deriv Title",
            200,  # Sample duration > total length
            180,
        )
    assert "Sample duration cannot exceed total track length" in str(exc.value)


def test_create_clearance_agreement_unregistered_work_rejection(direct_vm, direct_deploy, direct_bob):
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = direct_bob
    direct_vm.value = 2 * ATTO

    with pytest.raises(Exception) as exc:
        contract.create_clearance_agreement(
            "aggr-unregistered",
            "non-existent-work",
            "Deriv Title",
            10,
            100,
        )
    assert "not found" in str(exc.value)


# -----------------------------------------------------------------------------
# 4. Autonomous Musicology Consensus Tests
# -----------------------------------------------------------------------------
def test_evaluate_sample_clearance_approved(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy(CONTRACT_PATH)

    direct_vm.sender = direct_alice
    contract.register_original_work(
        "work-synths",
        "Vintage Synth Hook",
        "US-SYN-84-00202",
        "sha256:prophet-5-arpeggio",
    )

    direct_vm.sender = direct_bob
    direct_vm.value = 5 * ATTO
    contract.create_clearance_agreement(
        "aggr-edm-remix",
        "work-synths",
        "Cyber Odyssey 2026",
        30,
        150,  # 20% sample weight
    )

    # Mock Web2 MusicBrainz API and Multi-LLM Musicology Quorum
    mock_music_registry_oracle(direct_vm, {"isrc": "US-SYN-84-00202", "status": "active"})
    mock_ai_musicology(
        direct_vm,
        decision="APPROVED",
        similarity_score=80,
        rationale="Melodic lead hook sampled with key shift to A minor.",
    )

    contract.evaluate_sample_clearance(
        "aggr-edm-remix",
        "Spectrogram audio analysis: 30s stem extraction at 128 BPM.",
    )

    aggr = contract.get_agreement("aggr-edm-remix")
    assert aggr["status"] == "APPROVED_ACTIVE"
    # Sample Weight = 20%; Similarity = 80%; Combined = (20*60 + 80*40)/100 = (1200 + 3200)/100 = 44%
    # Split BPS = 44 * 50 = 2200 BPS (22.00% royalty split to original master owner)
    assert aggr["royalty_split_bps"] == 2200


def test_evaluate_sample_clearance_rejected(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy(CONTRACT_PATH)

    direct_vm.sender = direct_alice
    contract.register_original_work(
        "work-guitar",
        "Acoustic Guitar Lick",
        "US-GTR-90-00303",
        "sha256:acoustic-lick",
    )

    direct_vm.sender = direct_bob
    direct_vm.value = 3 * ATTO
    contract.create_clearance_agreement(
        "aggr-rejected-sample",
        "work-guitar",
        "Heavy Metal Track",
        10,
        100,
    )

    mock_music_registry_oracle(direct_vm)
    mock_ai_musicology(
        direct_vm,
        decision="REJECTED",
        similarity_score=10,
        rationale="Zero harmonic correlation; distinct chord progressions.",
    )

    contract.evaluate_sample_clearance(
        "aggr-rejected-sample",
        "Spectrogram audio analysis.",
    )

    aggr = contract.get_agreement("aggr-rejected-sample")
    assert aggr["status"] == "REJECTED"
    assert aggr["royalty_split_bps"] == 0


# -----------------------------------------------------------------------------
# 5. Streaming Royalty Deposit & Autonomous Splitting Tests
# -----------------------------------------------------------------------------
def test_deposit_streaming_royalties_success(direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie):
    contract = direct_deploy(CONTRACT_PATH)

    direct_vm.sender = direct_alice
    contract.register_original_work(
        "work-piano",
        "Jazz Piano Chord",
        "US-JAZ-75-00404",
        "sha256:rhodes-piano-groove",
    )

    direct_vm.sender = direct_bob
    direct_vm.value = 5 * ATTO
    contract.create_clearance_agreement(
        "aggr-lofi-beats",
        "work-piano",
        "Midnight Study Session",
        30,
        120,  # 25% sample weight
    )

    mock_music_registry_oracle(direct_vm)
    # 25% weight, 75% similarity -> Combined = (25*60 + 75*40)/100 = (1500 + 3000)/100 = 45% -> Split = 2250 BPS (22.5%)
    mock_ai_musicology(direct_vm, decision="APPROVED", similarity_score=75)
    contract.evaluate_sample_clearance("aggr-lofi-beats", "Audio proof")

    # Streaming distributor (Charlie) deposits 100 GEN streaming royalties
    direct_vm.sender = direct_charlie
    direct_vm.value = 100 * ATTO
    contract.deposit_streaming_royalties("aggr-lofi-beats")

    aggr = contract.get_agreement("aggr-lofi-beats")
    assert aggr["total_royalties_distributed_atto"] == str(100 * ATTO)

    overview = contract.get_protocol_overview()
    assert overview["total_royalties_split_atto"] == str(100 * ATTO)


def test_deposit_streaming_royalties_unapproved_rejection(direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie):
    contract = direct_deploy(CONTRACT_PATH)

    direct_vm.sender = direct_alice
    contract.register_original_work(
        "work-bass",
        "Slap Bass Groove",
        "US-BAS-80-00505",
        "sha256:slap-bass",
    )

    direct_vm.sender = direct_bob
    direct_vm.value = 2 * ATTO
    contract.create_clearance_agreement(
        "aggr-unapproved",
        "work-bass",
        "Funk Remix",
        10,
        100,
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

    direct_vm.sender = direct_alice
    contract.register_original_work(
        "work-vocal",
        "Vocal Adlib",
        "US-VOC-99-00606",
        "sha256:vocal-sample",
    )

    direct_vm.sender = direct_bob
    direct_vm.value = 2 * ATTO
    contract.create_clearance_agreement(
        "aggr-to-dispute",
        "work-vocal",
        "House Anthem",
        5,
        180,
    )

    # Master owner disputes sample
    direct_vm.sender = direct_alice
    contract.dispute_sample("aggr-to-dispute", "Uncredited lyric interpolation.")

    aggr = contract.get_agreement("aggr-to-dispute")
    assert aggr["status"] == "DISPUTED"


def test_list_original_works_and_agreements(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = direct_alice

    contract.register_original_work(
        "work-list-1",
        "Track One",
        "ISRC-1",
        "Hash-1",
    )

    direct_vm.sender = direct_bob
    direct_vm.value = 2 * ATTO
    contract.create_clearance_agreement(
        "aggr-list-1",
        "work-list-1",
        "Deriv One",
        10,
        100,
    )

    works = contract.list_original_works()
    assert len(works) == 1
    assert works[0]["work_id"] == "work-list-1"

    aggrs = contract.list_agreements("work-list-1")
    assert len(aggrs) == 1
    assert aggrs[0]["agreement_id"] == "aggr-list-1"
