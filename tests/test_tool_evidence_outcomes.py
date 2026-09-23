from nexus.runtime.evidence import EvidenceLedger


def test_explicit_success_outcome():
    ledger = EvidenceLedger()

    ledger.record(
        "read_file",
        {"path": "x"},
        "ok",
        outcome="EXECUTED_SUCCESSFULLY",
    )

    summary = ledger.summary()
    item = summary["tools"][0]

    assert item["success"] is True
    assert (
        item["outcome"]
        == "EXECUTED_SUCCESSFULLY"
    )
    assert summary["successful"] == 1
    assert summary["failed"] == 0


def test_policy_block_is_not_success():
    ledger = EvidenceLedger()

    ledger.record(
        "shell",
        {"command": "touch x"},
        "NEXUS_CAPABILITY_BLOCKED: READ_ONLY:shell",
        outcome="BLOCKED_BY_POLICY",
    )

    summary = ledger.summary()
    item = summary["tools"][0]

    assert item["success"] is False
    assert (
        item["outcome"]
        == "BLOCKED_BY_POLICY"
    )
    assert summary["successful"] == 0
    assert summary["failed"] == 1


def test_execution_failure_is_distinct():
    ledger = EvidenceLedger()

    ledger.record(
        "write_file",
        {"path": "x"},
        "TOOL_EXCEPTION=boom",
        outcome="EXECUTION_FAILED",
    )

    item = ledger.summary()["tools"][0]

    assert item["success"] is False
    assert (
        item["outcome"]
        == "EXECUTION_FAILED"
    )


def test_legacy_record_api_remains_supported():
    ledger = EvidenceLedger()

    ledger.record(
        "read_file",
        {},
        "contents",
    )

    ledger.record(
        "write_file",
        {},
        "NEXUS_PERMISSION_BLOCK=denied",
    )

    summary = ledger.summary()

    assert summary["successful"] == 1
    assert summary["failed"] == 1


def test_invalid_outcome_fails_closed():
    ledger = EvidenceLedger()

    try:
        ledger.record(
            "read_file",
            {},
            "ok",
            outcome="INVALID",
        )
    except ValueError as exc:
        assert (
            "INVALID_TOOL_EVIDENCE_OUTCOME"
            in str(exc)
        )
    else:
        raise AssertionError(
            "invalid outcome accepted"
        )
