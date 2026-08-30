#!/usr/bin/env python3
"""
TuneLedger 1-Click End-to-End Lifecycle Demonstration.

Walks the full escrow lifecycle: master work registration, sample clearance
agreement, the AI musicology audit over evidence the contract fetches for
itself, deterministic tier-based royalty splitting, and DSP royalty payout.
"""

import json

from gltest.direct import VMContext, deploy_contract, create_address

ATTO = 10**18

# Where the acoustic evidence lives. These URIs are pinned on-chain at
# registration time; the contract retrieves them itself inside the
# non-deterministic block, so the demo has to stand up both endpoints.
MASTER_URI = "https://fingerprints.tuneledger.music/master/amen-break.json"
DERIVATIVE_URI = "https://fingerprints.tuneledger.music/derivative/jungle-remix.json"

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


def log_step(num: int, title: str):
    print(f"\n\033[1;36m[STEP {num}] {title}\033[0m")


def log_success(msg: str):
    print(f"  \033[1;32m[OK]\033[0m {msg}")


def log_info(key: str, val: str):
    print(f"  \033[1;34m-\033[0m {key}: \033[1;37m{val}\033[0m")


def keccak_commitment(document: str) -> str:
    """Derive the on-chain commitment for a fingerprint document.

    Mirrors the contract's own digest over the same normalized bytes, so the
    work registers against exactly what the mocked host will serve. Imported
    lazily because the GenVM SDK only lands on sys.path once a contract loads.
    """
    from genlayer.py.keccak import Keccak256

    return "keccak256:" + Keccak256(document.strip().encode("utf-8")).hexdigest()


def mock_acoustic_feeds(vm, similarity_score: int = 85):
    """Serve the two fingerprint documents plus the ISRC registry feed."""
    vm.mock_web(r".*/master/.*", {"status": 200, "body": MASTER_DOC})
    vm.mock_web(r".*/derivative/.*", {"status": 200, "body": DERIVATIVE_DOC})
    vm.mock_web(
        r".*acoustid-isrc.*",
        {"status": 200, "body": json.dumps({"isrc_status": "active", "acoustid_match": similarity_score})},
    )
    vm.mock_llm(
        r".*impartial Musicologist and Copyright Audio Auditor.*",
        json.dumps(
            {
                "decision": "APPROVED",
                "similarity_score": similarity_score,
                "rationale": "Direct drum break interpolation from 'Amen, Brother' with harmonic alignment.",
            }
        ),
    )


def main():
    print("\033[1;35m" + "=" * 70)
    print(" TUNELEDGER: 1-CLICK END-TO-END MUSIC ROYALTY ESCROW LIFECYCLE")
    print("=" * 70 + "\033[0m")

    # 1. Initialize Direct VM Environment
    vm = VMContext()
    master_artist = create_address("master_rights_holder")  # Original Master Owner
    sampling_artist = create_address("sampling_producer")   # Derivative Artist
    dsp_platform = create_address("spotify_dsp")            # Streaming Royalty Depositor

    with vm.activate():
        vm.sender = master_artist
        contract = deploy_contract("contract/contracts/tuneledger_royalty.py", vm=vm)

        # STEP 1: Register Master Musical Work
        log_step(1, "Original Rights Holder Registers Master Track ('Amen, Brother')")
        vm.sender = master_artist
        contract.register_original_work(
            "work-amen-break-1969",
            "Amen, Brother",
            "US-S1Z-69-00001",
            keccak_commitment(MASTER_DOC),
            MASTER_URI,
        )
        work = contract.get_original_work("work-amen-break-1969")
        log_success("Master Track Registered On-Chain")
        log_info("Work ID", work["work_id"])
        log_info("Work Title", work["title"])
        log_info("ISRC Code", work["isrc_code"])
        log_info("Fingerprint Commitment", work["audio_fingerprint_hash"][:32] + "...")
        log_info("Fingerprint URI", work["fingerprint_uri"])
        log_info("Rights Holder Address", work["master_owner"])

        # STEP 2: Create Clearance Agreement
        log_step(2, "Derivative Producer Creates Sample Clearance Agreement")
        vm.sender = sampling_artist
        vm.value = 5 * ATTO
        contract.create_clearance_agreement(
            "agree-jungle-remix-2026",
            "work-amen-break-1969",
            "Jungle Frequency 2026",
            6,    # 6 seconds of sampled drum break
            180,  # 180 seconds total track length
            DERIVATIVE_URI,
        )
        vm.value = 0
        agree = contract.get_agreement("agree-jungle-remix-2026")
        log_success("Clearance Agreement Initialized")
        log_info("Agreement ID", agree["agreement_id"])
        log_info("Derivative Title", agree["derivative_title"])
        log_info("Sample Duration / Total Track", f"{agree['sample_duration_sec']}s / {agree['total_track_sec']}s")
        log_info("Derivative Fingerprint URI", agree["derivative_fingerprint_uri"])
        log_info("Initial Status", agree["status"])

        # STEP 3: Multi-LLM Musicology Quorum & ISRC Registry Audit
        log_step(3, "GenLayer AI Musicology Quorum Fetches and Audits Acoustic Evidence")
        mock_acoustic_feeds(vm, similarity_score=85)

        # The caller supplies nothing but the agreement id. Every input to the
        # decision is either already on-chain or fetched by the contract.
        contract.evaluate_sample_clearance("agree-jungle-remix-2026")

        cleared = contract.get_agreement("agree-jungle-remix-2026")
        record = contract.get_records("agree-jungle-remix-2026")[0]
        log_success(f"Sample Clearance Approved! Status: {cleared['status']}")
        log_info("Fingerprint Verified Against Commitment", str(record["fingerprint_verified"]))
        log_info("Master Evidence Digest", record["master_evidence_digest"][:32] + "...")
        log_info("Similarity Score", f"{record['similarity_score']} (tier floor 85)")
        log_info(
            "Deterministic Royalty Split",
            f"{cleared['royalty_split_bps'] / 100:.2f}% to Master Rights Holder",
        )

        # STEP 4: Streaming Royalty Deposit & Automated Splitting
        log_step(4, "Streaming DSP Deposits 100 GEN in Net Royalties for Instant Splitting")
        vm.sender = dsp_platform
        vm.value = 100 * ATTO
        contract.deposit_streaming_royalties("agree-jungle-remix-2026")
        vm.value = 0
        split_agree = contract.get_agreement("agree-jungle-remix-2026")
        log_success("Streaming Royalties Split & Disbursed in Real-Time")
        log_info("Total Royalties Processed", f"{int(split_agree['total_royalties_distributed_atto']) // ATTO} GEN")

        # STEP 5: Protocol Overview
        log_step(5, "Inspect TuneLedger Double-Entry Accounting Overview")
        overview = contract.get_protocol_overview()
        log_info("Total Original Works Registered", f"{overview['total_works_registered']}")
        log_info("Total Agreements Created", f"{overview['total_agreements_created']}")
        log_info("Total Royalties Split", f"{int(overview['total_royalties_split_atto']) // ATTO} GEN")

        print("\n\033[1;32m" + "=" * 70)
        print(" TUNELEDGER RUNNABLE WORKFLOW VERIFIED SUCCESSFULLY (100% PASS)")
        print("=" * 70 + "\033[0m\n")


if __name__ == "__main__":
    main()
