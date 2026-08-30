```text
  ___       ___       ___       ___       ___
 |###|     |###|     |###|     |###|     |###|
 |###|_____|###|_____|###|_____|###|_____|###|
 |#########################################|
   T U N E L E D G E R   //   A U D I O   D N A
```

# TuneLedger: Autonomous Audio Fingerprinting & Instant Music Royalty Splitting

> **Deterministic Sample Clearance, Chromaprint Spectrogram Quorum & Real-Time DSP Streaming Revenue Distribution on GenLayer.**

[![Network](https://img.shields.io/badge/GenLayer-StudioNet-FF4500.svg?style=for-the-badge&logo=soundcharts)](https://studio.genlayer.com)
[![Direct Tests](https://img.shields.io/badge/Direct_Tests-67%2F67_Passing-00E5FF.svg?style=for-the-badge)](contract/tests/)
[![Acoustic Engine](https://img.shields.io/badge/Acoustic_Engine-Chromaprint_Keccak256-FFD700.svg?style=for-the-badge)](contract/contracts/tuneledger_royalty.py)
[![License](https://img.shields.io/badge/License-MIT-purple.svg?style=for-the-badge)](LICENSE)

---

## Paradigm Shift: Legacy Publishing vs. TuneLedger

```text
+------------------------------------------------------------------------------+
|  OLD WORLD: Legacy Music Publishing                                          |
|  Sample Used -> 6 Months Lawyers -> 50% Legal Cut -> Delayed PRO Royalty      |
+------------------------------------------------------------------------------+
|  NEW WORLD: TuneLedger Intelligent Protocol                                  |
|  Sample Used -> Multi-LLM Musicology Quorum -> Fixed Tier BPS -> Real-Time $  |
+------------------------------------------------------------------------------+
```

| Operational Dimension | Traditional Music Industry | TuneLedger Autonomous Protocol |
| :--- | :--- | :--- |
| **Sample Clearance Speed** | 3 to 12 months of legal back-and-forth | **Instant Autonomous Resolution** via GenLayer Quorum |
| **Middleman Overhead** | 30% - 50% taken by publishers & lawyers | **Zero Intermediary Leakage** (100% direct artist payout) |
| **Harmonic Similarity** | Subjective courtroom hearings | **Deterministic Spectral & Chromaprint Analysis** |
| **DSP Royalty Lag** | 6 to 18 months payout latency (ASCAP/BMI) | **Real-Time Atomic Disbursal** on Spotify/DSP deposit |
| **Evidence Custody** | Parties submit their own exhibits | **Contract-Fetched Evidence** bound to an on-chain commitment |

---

## Safety Model: Why a Clearance Is Verifiable

Two properties make a royalty split safe to reach consensus on.

**1. The contract acquires its own evidence.** `evaluate_sample_clearance`
takes nothing but an agreement id. No caller ever hands the contract a
similarity score, an audio proof blob, or a URL at evaluation time. The
fingerprint URIs are pinned on-chain when the work is registered and when the
agreement is created, and the documents are retrieved with `gl.nondet.web.get`
*inside* the non-deterministic block. The fetched master bytes are hashed and
compared against the Keccak-256 commitment the rights holder registered up
front; evidence that does not match that commitment can never clear.

**2. The payout is bound exactly, not approximately.** A validator accepts a
leader result if and only if it settles to the identical `(decision, split_bps)`
pair as the validator's own reading, plus byte-identical evidence digests. There
is no numeric tolerance anywhere in the acceptance path. Raw similarity scores
are deliberately *not* compared directly: the score matters only through the
tier it selects, so two nodes reading 86 and 97 agree (both top tier), while 84
and 85 disagree (2800 vs 4000 bps) and are rejected.

---

## StudioNet Deployment Metadata

```yaml
Protocol Name: TuneLedger Music Royalty Engine
Chain Architecture: GenLayer StudioNet (Chain ID: 61999)
Contract Address: "0x33f31423C9C83c28026A2626525eAF1BF3909b82"
Deployer Account: "0x7e1437789960927eBa45A2E6237BDDdB8c422600"
Deployment Tx: "0x1ce7e8c4c0f6e6b899ad0705e744a61a04c4ab7d337b8af37665e9ac0902069a"
Status: ACTIVE_DEPLOYED
```

---

## Acoustic DNA & Harmonic Split Mechanics

The royalty split is a **step function** over two fixed integer tables. There is
no floating-point arithmetic and no interpolation anywhere in the path, so every
validator node derives a byte-identical result.

### 1. Similarity Tiers

The first tier whose floor the score meets wins. A score below 40 is not a
derivative work and never clears.

| Similarity Score | Base Split |
| :--- | :--- |
| 85 - 100 | 5000 bps (50.00%) |
| 70 - 84 | 3500 bps (35.00%) |
| 55 - 69 | 2500 bps (25.00%) |
| 40 - 54 | 1500 bps (15.00%) |
| 0 - 39 | rejected, 0 bps |

### 2. Sample Weight Bands

Sample weight is `(sample_duration_sec * 100) // total_track_sec`, integer
division. It scales the tier so a brief quotation and a wholesale lift do not
pay alike.

| Sample Weight | Scaling |
| :--- | :--- |
| 25% and above | 10000 bps (100% of tier) |
| 10% - 24% | 8000 bps (80% of tier) |
| 0% - 9% | 6000 bps (60% of tier) |

### 3. Final Allocation

```text
split_bps = clamp(500, (tier_bps * band_bps) // 10000, 5000)
```

Worked example, from the runnable demo: a 6-second sample of a 180-second track
scores 85. Weight is `(6 * 100) // 180 = 3%`, so the band is 6000 bps. The tier
is 5000 bps. Split is `(5000 * 6000) // 10000 = 3000 bps = 30.00%`.

Both tables are readable on-chain via `get_similarity_tiers()` and
`get_sample_weight_bands()`, and any split can be reproduced off-chain before
clearing with the pure view `preview_royalty_split()`.

---

## Intelligent Contract Interface

```python
# 1. Master owner registers the fingerprint COMMITMENT plus the URI the
#    contract will later fetch the document from for itself.
register_original_work(
    work_id="work-amen-break-1969",
    title="Amen, Brother",
    isrc_code="US-S1Z-69-00001",
    audio_fingerprint_hash="keccak256:287ab53e420caf78d49af7...",
    fingerprint_uri="https://fingerprints.tuneledger.music/master/amen-break.json",
)

# 2. Derivative producer requests clearance with a 5 GEN deposit, pinning the
#    derivative fingerprint URI so the evidence cannot be swapped afterwards.
create_clearance_agreement(
    agreement_id="agree-jungle-remix-2026",
    original_work_id="work-amen-break-1969",
    derivative_title="Jungle Frequency 2026",
    sample_duration_sec=6,
    total_track_sec=180,
    derivative_fingerprint_uri="https://fingerprints.tuneledger.music/derivative/jungle-remix.json",
)

# 3. The quorum fetches both documents, verifies the master against its
#    on-chain commitment, and settles to a discrete tier. The caller supplies
#    NO evidence -- only the agreement id.
evaluate_sample_clearance(agreement_id="agree-jungle-remix-2026")

# 4. Streaming DSP deposits 100 GEN -> instant automatic split to both artists
deposit_streaming_royalties(agreement_id="agree-jungle-remix-2026")
```

---

## Terminal Verification & Direct-Mode Tests

### 1-Click Runnable Lifecycle Demonstration:
```bash
.venv/bin/python scripts/e2e_demo.py
```

```text
======================================================================
 TUNELEDGER: 1-CLICK END-TO-END MUSIC ROYALTY ESCROW LIFECYCLE
======================================================================

[STEP 1] Original Rights Holder Registers Master Track ('Amen, Brother')
  [OK] Master Track Registered On-Chain
  - Work ID: work-amen-break-1969
  - Work Title: Amen, Brother
  - ISRC Code: US-S1Z-69-00001
  - Fingerprint Commitment: keccak256:287ab53e420caf78d49af7...
  - Fingerprint URI: https://fingerprints.tuneledger.music/master/amen-break.json
  - Rights Holder Address: 0xE572fAb58EBcf81F0117ecBb91BE22E35094fFdD

[STEP 2] Derivative Producer Creates Sample Clearance Agreement
  [OK] Clearance Agreement Initialized
  - Agreement ID: agree-jungle-remix-2026
  - Derivative Title: Jungle Frequency 2026
  - Sample Duration / Total Track: 6s / 180s
  - Derivative Fingerprint URI: https://fingerprints.tuneledger.music/derivative/jungle-remix.json
  - Initial Status: CLEARANCE_REQUESTED

[STEP 3] GenLayer AI Musicology Quorum Fetches and Audits Acoustic Evidence
  [OK] Sample Clearance Approved! Status: APPROVED_ACTIVE
  - Fingerprint Verified Against Commitment: True
  - Master Evidence Digest: keccak256:287ab53e420caf78d49af7...
  - Similarity Score: 85 (tier floor 85)
  - Deterministic Royalty Split: 30.00% to Master Rights Holder

[STEP 4] Streaming DSP Deposits 100 GEN in Net Royalties for Instant Splitting
  [OK] Streaming Royalties Split & Disbursed in Real-Time
  - Total Royalties Processed: 100 GEN

[STEP 5] Inspect TuneLedger Double-Entry Accounting Overview
  - Total Original Works Registered: 1
  - Total Agreements Created: 1
  - Total Royalties Split: 100 GEN

======================================================================
 TUNELEDGER RUNNABLE WORKFLOW VERIFIED SUCCESSFULLY (100% PASS)
======================================================================
```

### Full Pytest Direct-Mode Suite (67/67 Passed):
```bash
make test
```

```text
============================= test session starts ==============================
contract/tests/test_determinism.py ..................................... [ 55%]
contract/tests/test_tuneledger.py .........................              [100%]
============================== 67 passed in 1.52s ==============================
```

`test_determinism.py` (42 cases) is the consensus-safety suite. It drives the
contract's real captured `validator_fn` through gltest direct-mode replay,
re-mocking the fingerprint and LLM feeds between the leader run and the
validator run to simulate two nodes scoring the same pair of tracks
differently. It covers three directions:

- **SAFETY** - no pair of scores that disagree on the split is ever accepted,
  including every adjacent tier-boundary pair (39/40, 54/55, 69/70, 84/85).
- **LIVENESS** - scores that agree on the split are not spuriously rejected,
  including 85/100, which the old fixed-tolerance rule wrongly refused.
- **EVIDENCE** - nodes that fetched different audio never reach agreement, even
  when their similarity scores are identical.

The tier tables are additionally checked against a hand-written oracle that is
independent of the contract's own constants, so a silent change to a tier
boundary fails the suite rather than redefining what "correct" means.

### Lint

```bash
make lint
```
