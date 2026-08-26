```text
  ▄█▄       ▄█▄       ▄█▄       ▄█▄       ▄█▄ 
 █████ ▄█▄ █████ ▄█▄ █████ ▄█▄ █████ ▄█▄ █████
 █████████████████████████████████████████████
   T U N E L E D G E R   //   A U D I O   D N A
```

# 🎧 TuneLedger: Autonomous Audio Fingerprinting & Instant Music Royalty Splitting

> **Deterministic Sample Clearance, Chromaprint Spectrogram Quorum & Real-Time DSP Streaming Revenue Distribution on GenLayer.**

[![Network](https://img.shields.io/badge/GenLayer-StudioNet_Live-FF4500.svg?style=for-the-badge&logo=soundcharts)](https://studio.genlayer.com)
[![Direct Tests](https://img.shields.io/badge/Unit_Tests-13%2F13_Passing-00E5FF.svg?style=for-the-badge)](packages/tests/test_tuneledger.py)
[![Acoustic Engine](https://img.shields.io/badge/Acoustic_Engine-Chromaprint_SHA256-FFD700.svg?style=for-the-badge)](packages/contracts/tuneledger_royalty.py)
[![License](https://img.shields.io/badge/License-MIT-purple.svg?style=for-the-badge)](LICENSE)

---

## 🎹 Paradigm Shift: Legacy Publishing vs. TuneLedger

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  OLD WORLD: Legacy Music Publishing                                          │
│  Sample Used -> 6 Months Lawyers -> 50% Legal Cut -> Delayed PRO Royalty     │
├──────────────────────────────────────────────────────────────────────────────┤
│  NEW WORLD: TuneLedger Intelligent Protocol                                  │
│  Sample Used -> Multi-LLM Musicology Quorum -> Fair Split BPS -> Real-Time $ │
└──────────────────────────────────────────────────────────────────────────────┘
```

| Operational Dimension | Traditional Music Industry | TuneLedger Autonomous Protocol |
| :--- | :--- | :--- |
| **Sample Clearance Speed** | 3 to 12 months of legal back-and-forth | **Instant Autonomous Resolution** via GenLayer Quorum |
| **Middleman Overhead** | 30% - 50% taken by publishers & lawyers | **Zero Intermediary Leakage** (100% direct artist payout) |
| **Harmonic Similarity** | Subjective courtroom hearings | **Deterministic Spectral & Chromaprint Analysis** |
| **DSP Royalty Lag** | 6 to 18 months payout latency (ASCAP/BMI) | **Real-Time Atomic Disbursal** on Spotify/DSP deposit |
| **Escrow Safety** | Centralized escrow risk | **Zero-Deadlock Invariant**: Emergency unreviewed deposit release |

---

## 🛰️ StudioNet Deployment Metadata

```yaml
Protocol Name: TuneLedger Music Royalty Engine
Chain Architecture: GenLayer StudioNet (Chain ID: 61999)
Intelligent Contract: "0x4F86AaCFB5823dcc0CC4bb02E77D5384081f01ac"
Deployer Account: "0xB27ec487f3F808158f894CB2f3aac9a9E248F14F"
Deployment Tx: "0xa338e9c274668e81870c9d8040ef0131971f9e9accf36e3b1d87589681ca9e76"
```

---

## 🎼 Acoustic DNA & Harmonic Split Mechanics

TuneLedger computes fair-share royalty cuts using acoustic duration weighting combined with melodic similarity:

### 1. Sample Duration Weight ($W_{\text{sample}}$)
$$W_{\text{sample}} = \left(\frac{\text{Sample Duration (sec)}}{\text{Total Derivative Length (sec)}}\right) \times 100$$

### 2. Fair-Share Composite Score ($S$)
$$S = \frac{W_{\text{sample}} \times 0.60 + \text{Melodic Similarity (0-100)} \times 0.40}{100}$$

### 3. Basis Points Royalty Allocation ($\text{BPS}$)
$$\text{Royalty Split BPS} = \text{clamp}\Big(500, \, \lfloor S \times 5000 \rfloor, \, 5000\Big)$$

*Where $500 \text{ BPS} = 5.00\%$ and $5000 \text{ BPS} = 50.00\%$ maximum statutory sample split.*

---

## 🎛️ Intelligent Contract Interface

```python
# 1. Master owner registers audio fingerprint & ISRC code
register_original_work(
    work_id="work-amen-break-1969",
    title="Amen, Brother",
    isrc_code="US-S1Z-69-00001",
    audio_fingerprint_hash="sha256:chromaprint-acoustic-fingerprint-amen-break-solo"
)

# 2. Derivative producer requests sample clearance with 5 GEN deposit
create_clearance_agreement(
    agreement_id="agree-jungle-remix-2026",
    original_work_id="work-amen-break-1969",
    derivative_title="Jungle Frequency 2026",
    sample_duration_sec=6,
    total_track_sec=180
)

# 3. GenLayer AI Musicology Quorum audits audio similarity
evaluate_sample_clearance(
    agreement_id="agree-jungle-remix-2026",
    audio_proof_url="https://ipfs.io/ipfs/bafybeiaudiofilejunglefrequency2026"
)

# 4. Streaming DSP deposits 100 GEN -> Instant automatic split to both artists
deposit_streaming_royalties(agreement_id="agree-jungle-remix-2026")
```

---

## 🧪 Terminal Verification & Direct-Mode Tests

### 1-Click Runnable Lifecycle Demonstration:
```bash
python scripts/e2e_demo.py
```

```text
======================================================================
 🎵 TUNELEDGER: 1-CLICK END-TO-END MUSIC ROYALTY ESCROW LIFECYCLE
======================================================================

[STEP 1] Original Rights Holder Registers Master Track ('Amen, Brother')
  ✓ Master Track Registered On-Chain
  • Work ID: work-amen-break-1969
  • Work Title: Amen, Brother
  • ISRC Code: US-S1Z-69-00001
  • Rights Holder Address: 0xE572fAb58EBcf81F0117ecBb91BE22E35094fFdD

[STEP 2] Derivative Producer Creates Sample Clearance Agreement
  ✓ Clearance Agreement Initialized
  • Derivative Title: Jungle Frequency 2026
  • Sample Duration / Total Track: 6s / 180s
  • Initial Status: CLEARANCE_REQUESTED

[STEP 3] GenLayer AI Musicology Quorum Audits Acoustic Fingerprint & Similarity
  ✓ Sample Clearance Approved! Status: APPROVED_ACTIVE
  • Calculated Fair-Share Royalty Split: 17.50% to Master Rights Holder

[STEP 4] Streaming DSP Deposits 100 GEN in Net Royalties for Instant Splitting
  ✓ Streaming Royalties Split & Disbursed in Real-Time
  • Total Royalties Processed: 100 GEN

[STEP 5] Inspect TuneLedger Double-Entry Accounting Overview
  • Total Original Works Registered: 1
  • Total Agreements Created: 1
  • Total Royalties Split: 100 GEN

======================================================================
 🎉 TUNELEDGER RUNNABLE WORKFLOW VERIFIED SUCCESSFULLY (100% PASS)
======================================================================
```

### Full Pytest Direct-Mode Suite (13/13 Passed):
```bash
.venv/bin/pytest packages/tests/ -v
```

```text
packages/tests/test_tuneledger.py::test_initial_protocol_overview PASSED
packages/tests/test_tuneledger.py::test_register_original_work_success PASSED
packages/tests/test_tuneledger.py::test_register_original_work_empty_fields_rejection PASSED
packages/tests/test_tuneledger.py::test_register_duplicate_work_rejection PASSED
packages/tests/test_tuneledger.py::test_create_clearance_agreement_success PASSED
packages/tests/test_tuneledger.py::test_create_clearance_agreement_invalid_durations_rejection PASSED
packages/tests/test_tuneledger.py::test_create_clearance_agreement_unregistered_work_rejection PASSED
packages/tests/test_tuneledger.py::test_evaluate_sample_clearance_approved PASSED
packages/tests/test_tuneledger.py::test_evaluate_sample_clearance_rejected PASSED
packages/tests/test_tuneledger.py::test_deposit_streaming_royalties_success PASSED
packages/tests/test_tuneledger.py::test_deposit_streaming_royalties_unapproved_rejection PASSED
packages/tests/test_tuneledger.py::test_reclaim_unreviewed_deposit_success PASSED
packages/tests/test_tuneledger.py::test_list_original_works_and_agreements PASSED
============================== 13 passed in 0.25s ==============================
```
