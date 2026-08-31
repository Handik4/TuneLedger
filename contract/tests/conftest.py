"""Shared fixtures and mock helpers for TuneLedger direct-mode tests.

The contract fetches its own acoustic evidence, so tests must stand up three
distinct endpoints rather than one blanket web mock: the master fingerprint
document, the derivative fingerprint document, and the ISRC registry feed.
"""

import json

CONTRACT_PATH = "contract/contracts/tuneledger_royalty.py"
MUSIC_PROMPT_PATTERN = r".*impartial Musicologist and Copyright Audio Auditor.*"

ATTO = 10**18

# The URIs are pinned on-chain at registration time; these are what the tests
# register, and the patterns below are what the mocks answer on.
MASTER_URI = "https://fingerprints.tuneledger.music/master/amen-break.json"
DERIVATIVE_URI = "https://fingerprints.tuneledger.music/derivative/jungle-remix.json"

MASTER_PATTERN = r".*/master/.*"
DERIVATIVE_PATTERN = r".*/derivative/.*"
REGISTRY_PATTERN = r".*acoustid-isrc.*"

# Stand-in chromaprint documents. Content is irrelevant to the contract beyond
# its digest and the excerpt handed to the model, but keeping them realistic
# makes the prompt in a failing test readable.
MASTER_DOC = json.dumps(
    {
        "format": "chromaprint",
        "isrc": "US-S1Z-69-00001",
        "duration_sec": 6,
        "bpm": 136,
        "key": "G minor",
        "vector": [1912, 8823, 3341, 7710, 2205, 9184],
    }
)

DERIVATIVE_DOC = json.dumps(
    {
        "format": "chromaprint",
        "duration_sec": 180,
        "bpm": 174,
        "key": "G minor",
        "vector": [1912, 8823, 3341, 7710, 2207, 9188],
    }
)


def keccak_commitment(document: str) -> str:
    """Derive the on-chain commitment for a fingerprint document.

    Mirrors the contract's _keccak_hex over the same normalized bytes, so a work
    registered with this value verifies against the document the mock serves.
    Imported lazily because the GenVM SDK is only on sys.path once a contract
    has been loaded.
    """
    from genlayer.py.keccak import Keccak256

    return "keccak256:" + Keccak256(document.strip().encode("utf-8")).hexdigest()


def mock_fingerprint_evidence(
    direct_vm,
    master_doc: str = MASTER_DOC,
    derivative_doc: str = DERIVATIVE_DOC,
    master_status: int = 200,
    derivative_status: int = 200,
):
    """Serve the two fingerprint documents the contract retrieves for itself."""
    direct_vm.mock_web(MASTER_PATTERN, {"status": master_status, "body": master_doc})
    direct_vm.mock_web(DERIVATIVE_PATTERN, {"status": derivative_status, "body": derivative_doc})


def mock_music_registry_oracle(direct_vm, payload=None, status: int = 200):
    """Mock the Web2 music metadata API (MusicBrainz / ISRC / AcoustID)."""
    body = json.dumps(payload if payload is not None else {"status": "valid", "isrc_status": "registered"})
    direct_vm.mock_web(REGISTRY_PATTERN, {"status": status, "body": body})


def mock_ai_musicology(
    direct_vm,
    decision: str = "APPROVED",
    similarity_score: int = 80,
    rationale: str = "Clear sample interpolation detected in hook melody with harmonic alignment.",
):
    """Mock the Multi-LLM Quorum call for music sample clearance."""
    direct_vm.mock_llm(
        MUSIC_PROMPT_PATTERN,
        json.dumps(
            {
                "decision": decision,
                "similarity_score": similarity_score,
                "rationale": rationale,
            }
        ),
    )


def mock_full_audit(
    direct_vm,
    decision: str = "APPROVED",
    similarity_score: int = 80,
    master_doc: str = MASTER_DOC,
    derivative_doc: str = DERIVATIVE_DOC,
):
    """Register every external feed a clearance evaluation touches."""
    mock_fingerprint_evidence(direct_vm, master_doc=master_doc, derivative_doc=derivative_doc)
    mock_music_registry_oracle(direct_vm)
    mock_ai_musicology(direct_vm, decision=decision, similarity_score=similarity_score)


def register_work(
    contract,
    direct_vm,
    master_owner,
    work_id: str = "work-amen-break",
    title: str = "Amen, Brother",
    isrc: str = "US-S1Z-69-00001",
    master_doc: str = MASTER_DOC,
    fingerprint_uri: str = MASTER_URI,
):
    """Register a master work committed to the document the mocks will serve."""
    direct_vm.sender = master_owner
    contract.register_original_work(
        work_id,
        title,
        isrc,
        keccak_commitment(master_doc),
        fingerprint_uri,
    )
    return work_id


def create_agreement(
    contract,
    direct_vm,
    producer,
    agreement_id: str = "agree-jungle-remix",
    work_id: str = "work-amen-break",
    derivative_title: str = "Jungle Frequency 2026",
    sample_sec: int = 30,
    total_sec: int = 150,
    deposit_atto: int = 5 * ATTO,
    derivative_uri: str = DERIVATIVE_URI,
    derivative_fingerprint_hash: str = None,
    derivative_doc: str = DERIVATIVE_DOC,
):
    if derivative_fingerprint_hash is None:
        derivative_fingerprint_hash = keccak_commitment(derivative_doc)
    direct_vm.sender = producer
    direct_vm.value = deposit_atto
    contract.create_clearance_agreement(
        agreement_id,
        work_id,
        derivative_title,
        sample_sec,
        total_sec,
        derivative_uri,
        derivative_fingerprint_hash,
    )
    direct_vm.value = 0
    return agreement_id
