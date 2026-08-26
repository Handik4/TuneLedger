"""GenLayer Integration Test Suite for TuneLedger Royalty Protocol."""

import pytest
from gltest import get_contract_factory
from gltest.assertions import tx_execution_succeeded


def test_tuneledger_integration_flow():
    factory = get_contract_factory("TuneLedgerRoyalty")
    contract = factory.deploy(args=[])

    # 1. Register Original Master Work
    tx_work = contract.register_original_work(
        args=[
            "work-int-01",
            "Analog Modular Synth Hook",
            "US-MOD-85-00101",
            "sha256:moog-modular-sequence-120bpm",
        ]
    ).transact()
    assert tx_execution_succeeded(tx_work)

    # 2. Producer Requests Sample Clearance Agreement
    tx_aggr = contract.create_clearance_agreement(
        args=[
            "aggr-int-01",
            "work-int-01",
            "Deep House Sunset Remix",
            20,
            160,
        ],
        value=2 * 10**18,
    ).transact()
    assert tx_execution_succeeded(tx_aggr)

    # 3. Read Agreement State via .call()
    aggr = contract.get_agreement(args=["aggr-int-01"]).call()
    assert aggr["agreement_id"] == "aggr-int-01"
    assert aggr["status"] == "CLEARANCE_REQUESTED"
