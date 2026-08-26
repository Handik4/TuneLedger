# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

import json
from dataclasses import dataclass
from genlayer import *

# -----------------------------------------------------------------------------
# Domain Constants & Taxonomy
# -----------------------------------------------------------------------------
STATUS_REQUESTED = "CLEARANCE_REQUESTED"
STATUS_APPROVED = "APPROVED_ACTIVE"
STATUS_REJECTED = "REJECTED"
STATUS_DISPUTED = "DISPUTED"

DECISION_APPROVED = "APPROVED"
DECISION_REJECTED = "REJECTED"

ATTO = 10**18
MIN_CLEARANCE_FEE = 1 * ATTO    # 1 GEN minimum clearance deposit
MAX_ROYALTY_SPLIT_BPS = 5000     # 50.00% max sample royalty split
MIN_ROYALTY_SPLIT_BPS = 500      # 5.00% min sample royalty split

ERROR_EXPECTED = "[EXPECTED]"
ERROR_EXTERNAL = "[EXTERNAL]"
ERROR_LLM = "[LLM]"


# -----------------------------------------------------------------------------
# Storage Schemas
# -----------------------------------------------------------------------------
@allow_storage
@dataclass
class OriginalWork:
    work_id: str
    master_owner: Address
    title: str
    isrc_code: str
    audio_fingerprint_hash: str
    registered_seq: u256


@allow_storage
@dataclass
class ClearanceAgreement:
    agreement_id: str
    original_work_id: str
    derivative_producer: Address
    derivative_title: str
    sample_duration_sec: u256
    total_track_sec: u256
    clearance_deposit_atto: u256
    status: str
    royalty_split_bps: u256
    total_royalties_distributed_atto: u256
    registered_seq: u256


@allow_storage
@dataclass
class RoyaltyAuditRecord:
    agreement_id: str
    decision: str
    similarity_score: u256
    royalty_split_bps: u256
    rationale: str
    registry_feed_summary: str
    timestamp_seq: u256


@gl.evm.contract_interface
class _Recipient:
    class View:
        pass

    class Write:
        pass


# -----------------------------------------------------------------------------
# Intelligent Contract Interface
# -----------------------------------------------------------------------------
class TuneLedgerRoyalty(gl.Contract):
    owner: Address
    musicology_oracle_base: str

    total_works_registered: u256
    total_agreements_created: u256
    total_royalties_split_atto: u256

    # Master Works: work_id -> OriginalWork
    works: TreeMap[str, OriginalWork]
    work_ids: DynArray[str]

    # Clearance Agreements: agreement_id -> ClearanceAgreement
    agreements: TreeMap[str, ClearanceAgreement]
    agreement_ids: DynArray[str]

    # Global Audit Records
    records: DynArray[RoyaltyAuditRecord]

    def __init__(self, musicology_oracle_base: str = "https://api.tuneledger.music/v1/acoustid-isrc"):
        self.owner = gl.message.sender_address
        self.musicology_oracle_base = musicology_oracle_base
        self.total_works_registered = u256(0)
        self.total_agreements_created = u256(0)
        self.total_royalties_split_atto = u256(0)

    # ------------------------------------------------------------------
    # 1. Original Master Work Registration
    # ------------------------------------------------------------------
    @gl.public.write
    def register_original_work(
        self,
        work_id: str,
        title: str,
        isrc_code: str,
        audio_fingerprint_hash: str,
    ) -> None:
        if not work_id or len(work_id.strip()) == 0:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Work ID cannot be empty")
        if work_id in self.works:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Work {work_id} already registered")
        if not title or len(title.strip()) == 0:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Title cannot be empty")

        seq = u256(len(self.work_ids) + 1)
        work = OriginalWork(
            work_id=work_id,
            master_owner=gl.message.sender_address,
            title=title,
            isrc_code=isrc_code,
            audio_fingerprint_hash=audio_fingerprint_hash,
            registered_seq=seq,
        )

        self.works[work_id] = work
        self.work_ids.append(work_id)
        self.total_works_registered = u256(int(self.total_works_registered) + 1)

    # ------------------------------------------------------------------
    # 2. Sample Clearance Agreement Request
    # ------------------------------------------------------------------
    @gl.public.write.payable
    def create_clearance_agreement(
        self,
        agreement_id: str,
        original_work_id: str,
        derivative_title: str,
        sample_duration_sec: u256,
        total_track_sec: u256,
    ) -> None:
        if not agreement_id or len(agreement_id.strip()) == 0:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Agreement ID cannot be empty")
        if agreement_id in self.agreements:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Agreement {agreement_id} already exists")
        if original_work_id not in self.works:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Original work {original_work_id} not found")

        sample_sec = int(sample_duration_sec)
        total_sec = int(total_track_sec)
        if sample_sec <= 0 or total_sec <= 0:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Durations must be greater than zero")
        if sample_sec > total_sec:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Sample duration cannot exceed total track length")

        deposit = int(gl.message.value)
        if deposit < int(MIN_CLEARANCE_FEE):
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Minimum clearance deposit is 1 GEN")

        seq = u256(len(self.agreement_ids) + 1)
        aggr = ClearanceAgreement(
            agreement_id=agreement_id,
            original_work_id=original_work_id,
            derivative_producer=gl.message.sender_address,
            derivative_title=derivative_title,
            sample_duration_sec=sample_duration_sec,
            total_track_sec=total_track_sec,
            clearance_deposit_atto=u256(deposit),
            status=STATUS_REQUESTED,
            royalty_split_bps=u256(0),
            total_royalties_distributed_atto=u256(0),
            registered_seq=seq,
        )

        self.agreements[agreement_id] = aggr
        self.agreement_ids.append(agreement_id)
        self.total_agreements_created = u256(int(self.total_agreements_created) + 1)

    # ------------------------------------------------------------------
    # 3. Autonomous Musicology AI Consensus Evaluation
    # ------------------------------------------------------------------
    @gl.public.write
    def evaluate_sample_clearance(
        self,
        agreement_id: str,
        audio_analysis_proof: str,
        musicology_registry_url: str = "",
    ) -> None:
        if agreement_id not in self.agreements:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Agreement {agreement_id} not found")

        aggr = self.agreements[agreement_id]
        if aggr.status != STATUS_REQUESTED:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Agreement is not in REQUESTED status")

        work = self.works[aggr.original_work_id]
        oracle_url = musicology_registry_url if musicology_registry_url else f"{self.musicology_oracle_base}?isrc={work.isrc_code}"

        sample_sec = int(aggr.sample_duration_sec)
        total_sec = int(aggr.total_track_sec)
        sample_weight = (sample_sec * 100) // total_sec

        audit_res = self._evaluate_musicology_consensus(
            original_title=work.title,
            derivative_title=aggr.derivative_title,
            sample_weight=sample_weight,
            proof=audio_analysis_proof,
            oracle_url=oracle_url,
        )

        decision = str(audit_res.get("decision", DECISION_REJECTED))
        similarity = int(audit_res.get("similarity_score", 50))
        rationale = str(audit_res.get("rationale", "Musicology spectrogram evaluated."))
        registry_feed = str(audit_res.get("registry_feed_summary", "ISRC / AcoustID registry feed."))

        if decision == DECISION_APPROVED:
            # Mathematical Royalty Split Formulation:
            # Combined Weight = (SampleWeight * 0.60 + Similarity * 0.40)
            # Split BPS = min(5000, max(500, CombinedWeight * 50))
            combined_weight = (sample_weight * 60 + similarity * 40) // 100
            split_bps = min(MAX_ROYALTY_SPLIT_BPS, max(MIN_ROYALTY_SPLIT_BPS, combined_weight * 50))

            aggr.status = STATUS_APPROVED
            aggr.royalty_split_bps = u256(split_bps)

            # Disburse initial clearance deposit to original master owner
            dep = int(aggr.clearance_deposit_atto)
            if dep > 0:
                _Recipient(work.master_owner).emit_transfer(value=u256(dep), on="finalized")
        else:
            aggr.status = STATUS_REJECTED
            aggr.royalty_split_bps = u256(0)
            # Refund clearance deposit to derivative producer on rejection
            dep = int(aggr.clearance_deposit_atto)
            if dep > 0:
                _Recipient(aggr.derivative_producer).emit_transfer(value=u256(dep), on="finalized")

        self.agreements[agreement_id] = aggr

        rec = RoyaltyAuditRecord(
            agreement_id=agreement_id,
            decision=decision,
            similarity_score=u256(similarity),
            royalty_split_bps=aggr.royalty_split_bps,
            rationale=rationale,
            registry_feed_summary=registry_feed,
            timestamp_seq=u256(len(self.records) + 1),
        )
        self.records.append(rec)

    def _evaluate_musicology_consensus(
        self,
        original_title: str,
        derivative_title: str,
        sample_weight: int,
        proof: str,
        oracle_url: str,
    ) -> dict:
        def leader_fn() -> dict:
            meta_summary = "MusicBrainz ISRC verified: active copyright record."
            try:
                web_res = gl.nondet.web.render(oracle_url, mode="text")
                if web_res.status == 200 and web_res.body:
                    meta_summary = f"Registry returned: {web_res.body[:180]}"
            except Exception:
                meta_summary = "Direct spectrogram audio feature extraction."

            prompt = (
                "You are an impartial Musicologist and Copyright Audio Auditor. "
                f"Original Track: {original_title}. Derivative Track: {derivative_title}. "
                f"Sample Weight: {sample_weight}%. Audio Proof: {proof}. "
                f"Registry Metadata: {meta_summary}. "
                'Respond with strict JSON: {"decision": "APPROVED" | "REJECTED", '
                '"similarity_score": <int 0-100>, "rationale": "<summary>"}'
            )

            res = _run_musicology_llm(prompt)
            res["registry_feed_summary"] = meta_summary[:256]
            return res

        def validator_fn(leaders_res: gl.vm.Result) -> bool:
            if not isinstance(leaders_res, gl.vm.Return):
                return _handle_music_leader_error(leaders_res, leader_fn)
            try:
                v_res = leader_fn()
                leader = leaders_res.calldata
                if not isinstance(leader, dict):
                    return False
                if leader.get("decision") != v_res.get("decision"):
                    return False
                
                sim_diff = abs(int(v_res.get("similarity_score", 0)) - int(leader.get("similarity_score", 0)))
                return sim_diff <= 15
            except Exception:
                return False

        return gl.vm.run_nondet_unsafe(leader_fn, validator_fn)

    # ------------------------------------------------------------------
    # 4. Streaming Royalty Deposit & Autonomous Splitting
    # ------------------------------------------------------------------
    @gl.public.write.payable
    def deposit_streaming_royalties(self, agreement_id: str) -> None:
        if agreement_id not in self.agreements:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Agreement {agreement_id} not found")

        aggr = self.agreements[agreement_id]
        if aggr.status != STATUS_APPROVED:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Cannot split royalties on non-APPROVED agreement")

        revenue = int(gl.message.value)
        if revenue <= 0:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Royalty deposit must be greater than zero")

        work = self.works[aggr.original_work_id]
        split_bps = int(aggr.royalty_split_bps)

        original_share = (revenue * split_bps) // 10000
        derivative_share = revenue - original_share

        aggr.total_royalties_distributed_atto = u256(int(aggr.total_royalties_distributed_atto) + revenue)
        self.agreements[agreement_id] = aggr
        self.total_royalties_split_atto = u256(int(self.total_royalties_split_atto) + revenue)

        # Autonomous Split
        if original_share > 0:
            _Recipient(work.master_owner).emit_transfer(value=u256(original_share), on="finalized")
        if derivative_share > 0:
            _Recipient(aggr.derivative_producer).emit_transfer(value=u256(derivative_share), on="finalized")

    # ------------------------------------------------------------------
    # 5. Sample Dispute
    # ------------------------------------------------------------------
    @gl.public.write
    def dispute_sample(self, agreement_id: str, dispute_reason: str) -> None:
        if agreement_id not in self.agreements:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Agreement {agreement_id} not found")

        aggr = self.agreements[agreement_id]
        work = self.works[aggr.original_work_id]
        sender = gl.message.sender_address
        if sender != work.master_owner and sender != aggr.derivative_producer and sender != self.owner:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Only master owner or producer can dispute")

        aggr.status = STATUS_DISPUTED
        self.agreements[agreement_id] = aggr

    # ------------------------------------------------------------------
    # 6. View Methods & Protocol Overview
    # ------------------------------------------------------------------
    @gl.public.view
    def get_original_work(self, work_id: str) -> dict:
        if work_id not in self.works:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Work {work_id} not found")
        work = self.works[work_id]
        return {
            "work_id": work.work_id,
            "master_owner": work.master_owner.as_hex,
            "title": work.title,
            "isrc_code": work.isrc_code,
            "audio_fingerprint_hash": work.audio_fingerprint_hash,
            "registered_seq": int(work.registered_seq),
        }

    @gl.public.view
    def get_agreement(self, agreement_id: str) -> dict:
        if agreement_id not in self.agreements:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Agreement {agreement_id} not found")
        aggr = self.agreements[agreement_id]
        return {
            "agreement_id": aggr.agreement_id,
            "original_work_id": aggr.original_work_id,
            "derivative_producer": aggr.derivative_producer.as_hex,
            "derivative_title": aggr.derivative_title,
            "sample_duration_sec": int(aggr.sample_duration_sec),
            "total_track_sec": int(aggr.total_track_sec),
            "clearance_deposit_atto": str(int(aggr.clearance_deposit_atto)),
            "status": aggr.status,
            "royalty_split_bps": int(aggr.royalty_split_bps),
            "total_royalties_distributed_atto": str(int(aggr.total_royalties_distributed_atto)),
            "registered_seq": int(aggr.registered_seq),
        }

    @gl.public.view
    def get_records(self, agreement_id: str) -> list:
        out = []
        for r in self.records:
            if r.agreement_id == agreement_id:
                out.append({
                    "decision": r.decision,
                    "similarity_score": int(r.similarity_score),
                    "royalty_split_bps": int(r.royalty_split_bps),
                    "rationale": r.rationale,
                    "registry_feed_summary": r.registry_feed_summary,
                    "timestamp_seq": int(r.timestamp_seq),
                })
        return out

    @gl.public.view
    def list_original_works(self) -> list:
        out = []
        for wid in self.work_ids:
            out.append(self.get_original_work(wid))
        return out

    @gl.public.view
    def list_agreements(self, original_work_id: str) -> list:
        out = []
        for aid in self.agreement_ids:
            aggr = self.agreements[aid]
            if aggr.original_work_id == original_work_id:
                out.append(self.get_agreement(aid))
        return out

    @gl.public.view
    def get_protocol_overview(self) -> dict:
        return {
            "owner": self.owner.as_hex,
            "musicology_oracle_base": self.musicology_oracle_base,
            "total_works_registered": int(self.total_works_registered),
            "total_agreements_created": int(self.total_agreements_created),
            "total_royalties_split_atto": str(int(self.total_royalties_split_atto)),
        }


# --- Internal Helpers -----------------------------------------------------
def _run_musicology_llm(prompt: str) -> dict:
    try:
        raw = gl.nondet.exec_prompt(prompt, response_format="json")
    except Exception as e:
        raise gl.vm.UserError(f"{ERROR_LLM} LLM execution failed: {str(e)}")

    if isinstance(raw, str):
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("```", 1)[0]
        cleaned = cleaned.strip()
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()
        try:
            parsed = json.loads(cleaned)
        except Exception as e:
            raise gl.vm.UserError(f"{ERROR_LLM} Malformed JSON from LLM: {str(e)}")
    elif isinstance(raw, dict):
        parsed = raw
    else:
        raise gl.vm.UserError(f"{ERROR_LLM} LLM output is not a JSON object")

    raw_dec = str(parsed.get("decision", DECISION_REJECTED)).strip().upper()
    decision = DECISION_APPROVED if raw_dec in ("APPROVED", "VALID", "CLEARED") else DECISION_REJECTED
    similarity = max(0, min(100, int(parsed.get("similarity_score", 50))))
    rationale = str(parsed.get("rationale", "Audio similarity analyzed."))[:300]

    return {
        "decision": decision,
        "similarity_score": similarity,
        "rationale": rationale,
    }


def _handle_music_leader_error(leaders_res: gl.vm.Result, leader_fn) -> bool:
    leader_msg = leaders_res.calldata if isinstance(leaders_res.calldata, str) else str(leaders_res)
    if ERROR_EXPECTED in leader_msg or ERROR_EXTERNAL in leader_msg:
        try:
            leader_fn()
            return False
        except gl.vm.UserError as v_err:
            return (
                (ERROR_EXPECTED in str(v_err) and ERROR_EXPECTED in leader_msg)
                or (ERROR_EXTERNAL in str(v_err) and ERROR_EXTERNAL in leader_msg)
            )
        except Exception:
            return False
    return False
