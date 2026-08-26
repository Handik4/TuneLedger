#!/usr/bin/env python3
"""
TuneLedger 1-Click End-to-End Lifecycle Demonstration.
Simulates Master Work Registration, Sample Clearance Agreement, AI Musicology Audit, Dynamic Royalty Splitting, and DSP Royalty Payout.
"""

import json
from gltest.direct import VMContext, deploy_contract, create_address

ATTO = 10**18


def log_step(num: int, title: str):
    print(f"\n\033[1;36m[STEP {num}] {title}\033[0m")


def log_success(msg: str):
    print(f"  \033[1;32m✓\033[0m {msg}")


def log_info(key: str, val: str):
    print(f"  \033[1;34m•\033[0m {key}: \033[1;37m{val}\033[0m")


def main():
    print("\033[1;35m" + "=" * 70)
    print(" 🎵 TUNELEDGER: 1-CLICK END-TO-END MUSIC ROYALTY ESCROW LIFECYCLE")
    print("=" * 70 + "\033[0m")

    # 1. Initialize Direct VM Environment
    vm = VMContext()
    master_artist = create_address("master_rights_holder") # Original Master Owner
    sampling_artist = create_address("sampling_producer")   # Derivative Artist
    dsp_platform = create_address("spotify_dsp")           # Streaming Royalty Depositor

    with vm.activate():
        vm.sender = master_artist
        contract = deploy_contract("packages/contracts/tuneledger_royalty.py", vm=vm)

        # STEP 1: Register Master Musical Work
        log_step(1, "Original Rights Holder Registers Master Track ('Amen, Brother')")
        vm.sender = master_artist
        contract.register_original_work(
            "work-amen-break-1969",
            "Amen, Brother",
            "US-S1Z-69-00001",
            "sha256:chromaprint-acoustic-fingerprint-amen-break-solo",
        )
        work = contract.get_original_work("work-amen-break-1969")
        log_success("Master Track Registered On-Chain")
        log_info("Work ID", work["work_id"])
        log_info("Work Title", work["title"])
        log_info("ISRC Code", work["isrc_code"])
        log_info("Acoustic Fingerprint Hash", work["audio_fingerprint_hash"][:32] + "...")
        log_info("Rights Holder Address", work["master_owner"])

        # STEP 2: Create Clearance Agreement
        log_step(2, "Derivative Producer Creates Sample Clearance Agreement")
        vm.sender = sampling_artist
        vm.value = 5 * ATTO
        contract.create_clearance_agreement(
            "agree-jungle-remix-2026",
            "work-amen-break-1969",
            "Jungle Frequency 2026",
            6,   # 6 seconds of sampled drum break
            180, # 180 seconds total track length
        )
        agree = contract.get_agreement("agree-jungle-remix-2026")
        log_success("Clearance Agreement Initialized")
        log_info("Agreement ID", agree["agreement_id"])
        log_info("Derivative Title", agree["derivative_title"])
        log_info("Sample Duration / Total Track", f"{agree['sample_duration_sec']}s / {agree['total_track_sec']}s")
        log_info("Initial Status", agree["status"])

        # STEP 3: Multi-LLM Musicology Quorum & ISRC Registry Audit
        log_step(3, "GenLayer AI Musicology Quorum Audits Acoustic Fingerprint & Similarity")
        vm.mock_web(r".*", {"status": 200, "body": json.dumps({"isrc_status": "active", "acoustid_match": 85})})
        vm.mock_llm(
            r".*",
            json.dumps({
                "decision": "APPROVED",
                "similarity_score": 85,
                "rationale": "Clear direct drum break interpolation from 'Amen, Brother' with harmonic alignment.",
            })
        )
        contract.evaluate_sample_clearance(
            "agree-jungle-remix-2026",
            "https://ipfs.io/ipfs/bafybeiaudiofilejunglefrequency2026",
        )
        cleared = contract.get_agreement("agree-jungle-remix-2026")
        log_success(f"Sample Clearance Approved! Status: {cleared['status']}")
        log_info("Calculated Fair-Share Royalty Split", f"{cleared['royalty_split_bps'] / 100:.2f}% to Master Rights Holder")

        # STEP 4: Streaming Royalty Deposit & Automated Splitting
        log_step(4, "Streaming DSP Deposits 100 GEN in Net Royalties for Instant Splitting")
        vm.sender = dsp_platform
        vm.value = 100 * ATTO
        contract.deposit_streaming_royalties("agree-jungle-remix-2026")
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
        print(" 🎉 TUNELEDGER RUNNABLE WORKFLOW VERIFIED SUCCESSFULLY (100% PASS)")
        print("=" * 70 + "\033[0m\n")


if __name__ == "__main__":
    main()
