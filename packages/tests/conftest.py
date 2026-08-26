"""Shared fixtures and mock helpers for TuneLedger direct-mode tests."""

import json

CONTRACT_PATH = "packages/contracts/tuneledger_royalty.py"
MUSIC_PROMPT_PATTERN = r".*impartial Musicologist and Copyright Audio Auditor.*"


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


def mock_music_registry_oracle(direct_vm, payload=None, status: int = 200):
    """Mock the Web2 music metadata API (MusicBrainz / ISRC / AcoustID)."""
    body = json.dumps(payload if payload is not None else {"status": "valid", "isrc_status": "registered"})
    direct_vm.mock_web(r".*", {"status": status, "body": body})
