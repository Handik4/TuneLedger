# TuneLedger Constitution — Music Copyright, Sample Clearance & Royalty Escrow Protocol

## Core Invariants & Governance Principles

### I. Provable Copyright Ownership & Derivative Splitting
1. Master rights and original works are registered with immutable audio fingerprint commitments and ISRC identifiers.
2. Derivative works (samples, remixes, interpolations) establish binding on-chain royalty splits with the original rightsholder upon clearance.

### II. Autonomous Musicology Consensus & Audio Fingerprint Ingestion
1. Sample clearance evaluation MUST use GenLayer's non-deterministic consensus (`gl.vm.run_nondet_unsafe`).
2. Online registry data (MusicBrainz, ISRC databases, AcoustID) is fetched via `gl.nondet.web.render`.
3. The Multi-LLM Musicology Quorum analyzes audio analysis spectrograms, key signatures, duration ratios, and melodic overlap to calculate deterministic royalty splits.

### III. Mathematical Royalty Distribution
1. Streaming royalties deposited into the escrow are split automatically:
   $$\text{Royalty Split BPS} = \min\left(5000, \max\left(500, \frac{W \times 0.60 + S \times 0.40}{100} \times 5000\right)\right)$$
2. Original master owners receive $\text{Royalty Split BPS} / 10000$, derivative producers receive the remainder.

### IV. GenVM Storage & Deterministic Execution
1. All balances use `u256` atto-precision ($10^{18}$).
2. Storage types MUST use `TreeMap` and `DynArray` with `@allow_storage` dataclasses.
3. 100% compliance with `genvm-lint` rules.
