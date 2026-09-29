import json
import tempfile
import unittest
from pathlib import Path

import yaml

from learning_project.cli import _build_parser
from learning_project.lab03 import (
    ExposureLedger,
    aggregate as aggregate_lab03,
    build_blinded_index,
    build_positions,
    check_near_duplicates,
    classify_failure,
    close_unstarted_positions,
    freeze_protocol,
    ingest_curator_candidate,
    load_family,
    load_frozen_instructions,
    record_assessment,
    record_completion_status,
    record_curator_attempt_failure,
    record_dispute,
    record_evaluator_amendment,
    record_recommendation,
    record_regression,
    record_interrupted_position,
    record_selected_comparison,
    record_transfer_case,
    record_variant_b,
    run_position,
    select_family,
    start_calibration,
    structural_check,
    submit_calibration,
    verify_lab03,
)
from learning_project.lab03_adapters import instructions_for
from learning_project.workflow import WorkflowError

TRAINING_PROJECT = Path(__file__).resolve().parent.parent.parent
CASES = TRAINING_PROJECT / "cases" / "lab03"
RESERVES = CASES / "reserves"
INSTRUCTIONS = TRAINING_PROJECT / "instructions" / "lab03"
CALIBRATION = CASES / "calibration"
AUTHORED_FAILURE = CASES / "authored-failure" / "authored-failure.json"

STUDENT = "student-01"


def fixture_runner(request: dict) -> str:
    return json.dumps(
        {"case_id": request["case_id"], "proposed_text": "Fixture answer grounded in the source."},
        ensure_ascii=False,
    )


class Lab03FamilyContractTests(unittest.TestCase):
    def test_all_course_reserve_families_load(self) -> None:
        families = [load_family(p) for p in sorted(RESERVES.glob("*/family.json"))]
        self.assertEqual(len(families), 3)
        check_near_duplicates(families)

    def test_development_inputs_load_with_two_cases(self) -> None:
        family = load_family(CASES / "development" / "dev-common-inputs.json", expected_cases=2)
        self.assertEqual(len(family["cases"]), 2)

    def test_family_with_a_missing_evidence_situation_is_rejected(self) -> None:
        family = load_family(RESERVES / "reserve-criteria-chain" / "family.json")
        family["cases"] = family["cases"][:3]
        family["expected_behaviors"] = family["expected_behaviors"][:3]
        path = Path(tempfile.mkdtemp()) / "broken-family.json"
        path.write_text(json.dumps(family), encoding="utf-8")
        with self.assertRaises(WorkflowError):
            load_family(path)

    def test_near_duplicate_case_text_across_families_is_rejected(self) -> None:
        first = load_family(RESERVES / "reserve-criteria-chain" / "family.json")
        second = load_family(RESERVES / "reserve-experiment-discipline" / "family.json")
        second["cases"][0]["task"] = first["cases"][0]["task"]
        second["cases"][0]["supplied_source"] = first["cases"][0]["supplied_source"]
        with self.assertRaises(WorkflowError):
            check_near_duplicates([first, second])


class Lab03FailureClassificationTests(unittest.TestCase):
    def test_authentication_quota_and_rate_limit_are_route_wide(self) -> None:
        for message in (
            "openrouter authentication failed: key is not set",
            "HTTP 429: rate limit exceeded",
            "account quota exhausted",
        ):
            self.assertEqual(classify_failure(message), "route-wide")

    def test_malformed_output_is_position_specific(self) -> None:
        self.assertEqual(classify_failure("response is not valid JSON"), "position-specific")

    def test_timeout_is_position_specific_even_with_unavailable_wording(self) -> None:
        self.assertEqual(
            classify_failure("openrouter route unavailable: timed out after 120s"),
            "position-specific",
        )


class Lab03CalibrationTests(unittest.TestCase):
    def test_calibration_flow_compares_student_and_reviewed_labels(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report_dir = Path(temp)
            path = start_calibration(
                report_dir=report_dir, packet_id="calibration-a", packets_dir=CALIBRATION, student=STUDENT
            )
            labels = yaml.safe_load(path.read_text(encoding="utf-8"))
            answers = {"cal-a-1": "S", "cal-a-2": "I", "cal-a-3": "U", "cal-a-4": "Q"}
            for item in labels["labels"]:
                item["category"] = answers[item["output_id"]]
                item["rationale"] = "test rationale"
            path.write_text(yaml.safe_dump(labels), encoding="utf-8")
            result = submit_calibration(
                report_dir=report_dir, packet_id="calibration-a", packets_dir=CALIBRATION, student=STUDENT
            )
            self.assertEqual(result["agreement"], 4)
            with self.assertRaises(WorkflowError):
                start_calibration(
                    report_dir=report_dir, packet_id="calibration-a", packets_dir=CALIBRATION, student=STUDENT
                )


class Lab03WorkflowTests(unittest.TestCase):
    def _prepare_development(self, report_dir: Path) -> None:
        record_transfer_case(
            report_dir=report_dir,
            transfer_case={
                "case_id": "transfer-approval",
                "task": "State who approves requests.",
                "supplied_source": "A supervisor approves requests.",
                "provenance": "public test scenario",
            },
            perturbation={
                "case_id": "transfer-approval-perturbed",
                "task": "State who approves requests.",
                "supplied_source": "A supervisor records requests.",
                "provenance": "public test scenario",
                "perturbation_note": "verb changed",
                "expectation": "authority claim must disappear",
            },
        )
        record_variant_b(
            report_dir=report_dir,
            variant_b_text="Variant B text for tests.",
            change_declaration={
                "changed_property": "length bound",
                "mechanism": "bounded paragraph",
                "declared_factors": ["length bound"],
            },
        )
        self._seed_terminal_development(report_dir)

    def _seed_terminal_development(self, report_dir: Path) -> None:
        case_ids = ["dev-criteria", "dev-authority", "transfer-approval", "transfer-approval-perturbed"]
        positions = []
        for index, case_id in enumerate(case_ids):
            for variant in ("a", "b"):
                positions.append(
                    {
                        "position_id": f"pos-{case_id}-{variant}-1",
                        "case_id": case_id,
                        "case_index": index,
                        "variant": variant,
                        "attempt": 1,
                        "state": "returned",
                    }
                )
        order = [p["position_id"] for p in positions if p["variant"] == "a"] + [
            p["position_id"] for p in positions if p["variant"] == "b"
        ]
        schedule = {
            "schema_version": "1.0",
            "kind": "development",
            "family_id": "dev-common",
            "order": order,
            "positions": positions,
        }
        path = report_dir / "development" / "schedule.json"
        path.write_text(json.dumps(schedule, indent=2) + "\n", encoding="utf-8")

    def _protocol(self) -> dict:
        return {
            "engineering_decision": "adopt B only if at least as supported as A",
            "hypothesis": "B reduces unsupported additions",
            "semantic_acceptance": "B has no more critical unsupported than A",
            "blocking_failures": "critical unsupported on a sufficient-evidence case",
            "operational_acceptance": "Observed latency must remain below 30 seconds; cost and tokens are excluded.",
            "tradeoff_rule": "Choose B only for fewer critical unsupported outcomes without worse acceptance.",
            "recommendation_precedence": {
                "decisive_rejection": "reject both on blockers",
                "uncertainty": "seek evidence only when it can change the decision",
                "positive_selection": "B needs a justified advantage",
                "no_justified_change": "retain acceptable A",
            },
            "attempt_budget": 16,
            "order_rule": "schedule order",
            "timing_boundary": "one session",
            "resume_window": "48h",
            "route": {"adapter": "offline-fixture", "model_id": "offline-fixture"},
        }

    def test_full_heldout_lifecycle_reaches_passed_complete(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report_dir = Path(temp)
            self._prepare_development(report_dir)
            ledger = ExposureLedger(report_dir / "exposure-ledger.json")
            manifest = freeze_protocol(
                report_dir=report_dir,
                protocol=self._protocol(),
                reserves_dir=RESERVES,
                ledger=ledger,
                student=STUDENT,
            )
            family = select_family(
                reserves_dir=RESERVES, ledger=ledger, freeze_manifest=manifest, student=STUDENT
            )
            comparison_dir = Path(manifest["comparison_dir"])
            revealed = json.loads((comparison_dir / "revealed-family.json").read_text(encoding="utf-8"))
            self.assertNotIn("expected_behaviors", revealed["family"])
            positions = build_positions(comparison_dir=comparison_dir, family=family, kind="held-out")
            self.assertEqual(len(positions), 16)
            schedule = json.loads((comparison_dir / "schedule.json").read_text(encoding="utf-8"))
            cases_by_id = {c["case_id"]: c for c in family["cases"]}
            instructions = load_frozen_instructions(comparison_dir)
            for position_id in schedule["order"]:
                result = run_position(
                    comparison_dir=comparison_dir,
                    schedule=json.loads((comparison_dir / "schedule.json").read_text(encoding="utf-8")),
                    position_id=position_id,
                    cases_by_id=cases_by_id,
                    instructions=instructions,
                    runner=fixture_runner,
                    adapter="offline-fixture",
                    model_id="offline-fixture",
                    recorded_by=STUDENT,
                )
                self.assertEqual(result["outcome"], "returned")
            index = build_blinded_index(comparison_dir=comparison_dir, family=family)
            self.assertEqual(len(index["entries"]), 16)
            scoring_view = json.loads((comparison_dir / "scoring" / "scoring-view.json").read_text(encoding="utf-8"))
            join_map = json.loads((comparison_dir / "scoring" / "_join-map.json").read_text(encoding="utf-8"))
            self.assertEqual(len(scoring_view["items"]), 16)
            self.assertTrue(join_map["entries"])
            for item in scoring_view["items"]:
                self.assertNotIn("expected_category", item)
                self.assertNotIn("position_id", item)
                self.assertNotIn("variant", item)
                self.assertEqual(item["proposed_text"], "Fixture answer grounded in the source.")
            for entry in index["entries"]:
                record_assessment(
                    comparison_dir=comparison_dir,
                    blind_id=entry["blind_id"],
                    assessment={
                        "category": entry["expected_category"],
                        "source_pointer": "supplied source",
                        "rationale": "test rationale",
                    },
                )
            record_selected_comparison(
                report_dir=report_dir, comparison_id=manifest["freeze_id"], student=STUDENT
            )
            aggregate_lab03(comparison_dir=comparison_dir)
            record_recommendation(
                comparison_dir=comparison_dir,
                outcome="seek-more-evidence",
                rationale="fixture evidence carries no live signal",
                limitations=["offline fixture"],
                student=STUDENT,
            )
            record_regression(
                report_dir=report_dir,
                regression={
                    "regression_id": "test-regression",
                    "source_kind": "authored-fixture",
                    "fixture_id": "authored-failure-supported-plus-invented",
                    "model_authorship_claim": "none",
                    "diagnosis": "unsupported added claim",
                    "expected_behavior_review": "supported answers add nothing",
                    "reviewed_by": STUDENT,
                },
            )
            (report_dir / "REPORT.md").write_text("# Report\n", encoding="utf-8")
            record_completion_status(
                report_dir=report_dir,
                status="complete",
                detail={"executed_positions": 16},
            )
            verification = verify_lab03(report_dir=report_dir, final_commit="a" * 40)
            self.assertEqual(verification["outcome"], "passed-complete")

    def test_route_wide_failure_and_honest_partial_completion(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report_dir = Path(temp)
            self._prepare_development(report_dir)
            ledger = ExposureLedger(report_dir / "exposure-ledger.json")
            manifest = freeze_protocol(
                report_dir=report_dir,
                protocol=self._protocol(),
                reserves_dir=RESERVES,
                ledger=ledger,
                student=STUDENT,
            )
            family = select_family(
                reserves_dir=RESERVES, ledger=ledger, freeze_manifest=manifest, student=STUDENT
            )
            comparison_dir = Path(manifest["comparison_dir"])
            build_positions(comparison_dir=comparison_dir, family=family, kind="held-out")
            schedule = json.loads((comparison_dir / "schedule.json").read_text(encoding="utf-8"))
            first_id = schedule["order"][0]
            instructions = load_frozen_instructions(comparison_dir)

            def failing_runner(request: dict) -> str:
                raise RuntimeError("authentication failed for the route")

            result = run_position(
                comparison_dir=comparison_dir,
                schedule=json.loads((comparison_dir / "schedule.json").read_text(encoding="utf-8")),
                position_id=first_id,
                cases_by_id={c["case_id"]: c for c in family["cases"]},
                instructions=instructions,
                runner=failing_runner,
                adapter="offline-fixture",
                model_id="offline-fixture",
                recorded_by=STUDENT,
            )
            self.assertEqual(result, {
                "position_id": first_id,
                "outcome": "failed",
                "failure_class": "route-wide",
            })
            with self.assertRaises(WorkflowError):
                run_position(
                    comparison_dir=comparison_dir,
                    schedule=json.loads((comparison_dir / "schedule.json").read_text(encoding="utf-8")),
                    position_id=schedule["order"][1],
                    cases_by_id={c["case_id"]: c for c in family["cases"]},
                    instructions=instructions,
                    runner=fixture_runner,
                    adapter="offline-fixture",
                    model_id="offline-fixture",
                    recorded_by=STUDENT,
                )
            closure = close_unstarted_positions(
                comparison_dir=comparison_dir, reason="route unavailable", student=STUDENT
            )
            self.assertEqual(len(closure["closed_positions"]), 15)
            (report_dir / "REPORT.md").write_text("Partial completion report.\n", encoding="utf-8")
            record_completion_status(
                report_dir=report_dir,
                status="honest-partial",
                detail={"executed_positions": 1, "closed_unstarted": 15},
            )
            verification = verify_lab03(report_dir=report_dir, final_commit="b" * 40)
            self.assertEqual(verification["outcome"], "passed-partial")

    def test_premature_exposure_removes_family_from_selection(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report_dir = Path(temp)
            ledger = ExposureLedger(report_dir / "exposure-ledger.json")
            from learning_project.lab03 import eligible_families, record_premature_exposure

            before = eligible_families(RESERVES, ledger, freeze_at=None)
            record_premature_exposure(ledger=ledger, family_id=before[0], student=STUDENT)
            after = eligible_families(RESERVES, ledger, freeze_at=None)
            self.assertNotIn(before[0], after)
            self.assertEqual(len(after), len(before) - 1)

    def test_structural_check_rejects_envelope_with_extra_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            comparison_dir = Path(temp)
            (comparison_dir / "schedule.json").write_text(
                json.dumps({
                    "positions": [
                        {"position_id": "pos-x-a-1", "case_id": "case-x", "state": "returned"}
                    ]
                }),
                encoding="utf-8",
            )
            attempt_dir = comparison_dir / "attempts" / "pos-x-a-1"
            attempt_dir.mkdir(parents=True)
            (attempt_dir / "raw-response.txt").write_text(
                json.dumps({"case_id": "case-x", "proposed_text": "ok", "extra": 1}), encoding="utf-8"
            )
            result = structural_check(comparison_dir=comparison_dir, position_id="pos-x-a-1")
            self.assertFalse(result["valid"])

    def test_curator_candidate_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            comparison_dir = Path(temp)
            prior = load_family(RESERVES / "reserve-criteria-chain" / "family.json")
            curator_input = {
                "prior_families": [
                    {
                        "family_id": prior["family_id"],
                        "cases": prior["cases"],
                        "expected_behaviors": prior["expected_behaviors"],
                    }
                ]
            }
            candidate = load_family(RESERVES / "reserve-experiment-discipline" / "family.json")
            candidate = json.loads(json.dumps(candidate))  # deep copy
            candidate["family_id"] = "curator-new-family"
            for case in candidate["cases"]:
                case["family_id"] = "curator-new-family"
                case["task"] = case["task"] + " (curator)"
            for behavior in candidate["expected_behaviors"]:
                pass  # behavior case ids still match
            family = ingest_curator_candidate(
                comparison_dir=comparison_dir,
                candidate_family=candidate,
                curator_input=curator_input,
                curator_session="curator-session-01",
            )
            self.assertEqual(family["origin"], "curator-generated")
            self.assertIn("curator_session", family["provenance"])
            self.assertTrue(
                (comparison_dir / "curator" / "attempts" / "attempt-1" / "result.yaml").exists()
            )

    def test_curator_attempts_are_bounded_and_sequential(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            comparison_dir = Path(temp)
            with self.assertRaises(WorkflowError):
                record_curator_attempt_failure(
                    comparison_dir=comparison_dir,
                    attempt=2,
                    outcome="empty-result",
                    detail="no content",
                    student=STUDENT,
                )
            record_curator_attempt_failure(
                comparison_dir=comparison_dir,
                attempt=1,
                outcome="route-unavailable",
                detail="provider unavailable",
                student=STUDENT,
            )
            record_curator_attempt_failure(
                comparison_dir=comparison_dir,
                attempt=2,
                outcome="empty-result",
                detail="no content",
                student=STUDENT,
            )
            with self.assertRaises(WorkflowError):
                record_curator_attempt_failure(
                    comparison_dir=comparison_dir,
                    attempt=2,
                    outcome="empty-result",
                    detail="retry beyond immutable attempt",
                    student=STUDENT,
                )

    def test_variant_a_can_run_before_variant_b_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report_dir = Path(temp)
            instructions = instructions_for(
                report_dir,
                TRAINING_PROJECT,
                required_variants={"a"},
            )
            self.assertEqual(set(instructions), {"a"})
            self.assertIn("exactly two fields", instructions["a"])

    def test_written_development_records_are_validated(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report_dir = Path(temp)
            self._prepare_development(report_dir)
            self.assertTrue((report_dir / "development" / "variant-b.txt").exists())
            with self.assertRaises(WorkflowError):
                record_variant_b(
                    report_dir=report_dir,
                    variant_b_text="Different text.",
                    change_declaration={
                        "changed_property": "a",
                        "mechanism": "m",
                        "declared_factors": ["a", "b"],
                    },
                )

    def test_variant_b_is_write_once(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report_dir = Path(temp)
            record_transfer_case(
                report_dir=report_dir,
                transfer_case={
                    "case_id": "transfer-approval",
                    "task": "State who approves requests.",
                    "supplied_source": "A supervisor approves requests.",
                    "provenance": "public test scenario",
                },
                perturbation={
                    "case_id": "transfer-approval-perturbed",
                    "task": "State who approves requests.",
                    "supplied_source": "A supervisor records requests.",
                    "provenance": "public test scenario",
                    "perturbation_note": "verb changed",
                    "expectation": "authority claim must disappear",
                },
            )
            record_variant_b(
                report_dir=report_dir,
                variant_b_text="First Variant B.",
                change_declaration={
                    "changed_property": "length bound",
                    "mechanism": "bounded paragraph",
                    "declared_factors": ["length bound"],
                },
            )
            with self.assertRaises(WorkflowError):
                record_variant_b(
                    report_dir=report_dir,
                    variant_b_text="Second Variant B.",
                    change_declaration={
                        "changed_property": "length bound",
                        "mechanism": "bounded paragraph",
                        "declared_factors": ["length bound"],
                    },
                )
            self.assertEqual(
                (report_dir / "development" / "variant-b.txt").read_text(encoding="utf-8"),
                "First Variant B.",
            )

    def test_freeze_snapshots_exact_bytes_and_refuses_digest_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report_dir = Path(temp)
            self._prepare_development(report_dir)
            ledger = ExposureLedger(report_dir / "exposure-ledger.json")
            manifest = freeze_protocol(
                report_dir=report_dir,
                protocol=self._protocol(),
                reserves_dir=RESERVES,
                ledger=ledger,
                student=STUDENT,
            )
            comparison_dir = Path(manifest["comparison_dir"])
            variant_a_bytes = (INSTRUCTIONS / "variant-a.txt").read_bytes()
            variant_b_bytes = (report_dir / "development" / "variant-b.txt").read_bytes()
            self.assertEqual((comparison_dir / "snapshots" / "variant-a.txt").read_bytes(), variant_a_bytes)
            self.assertEqual((comparison_dir / "snapshots" / "variant-b.txt").read_bytes(), variant_b_bytes)
            frozen = load_frozen_instructions(comparison_dir)
            self.assertEqual(frozen["a"].encode("utf-8"), variant_a_bytes)
            self.assertEqual(frozen["b"].encode("utf-8"), variant_b_bytes)
            (comparison_dir / "snapshots" / "variant-b.txt").write_bytes(variant_b_bytes + b" ")
            with self.assertRaises(WorkflowError):
                load_frozen_instructions(comparison_dir)

    def test_freeze_requires_terminal_development_structured_route_and_bindings(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report_dir = Path(temp)
            record_transfer_case(
                report_dir=report_dir,
                transfer_case={
                    "case_id": "transfer-approval",
                    "task": "State who approves requests.",
                    "supplied_source": "A supervisor approves requests.",
                    "provenance": "public test scenario",
                },
                perturbation={
                    "case_id": "transfer-approval-perturbed",
                    "task": "State who approves requests.",
                    "supplied_source": "A supervisor records requests.",
                    "provenance": "public test scenario",
                    "perturbation_note": "verb changed",
                    "expectation": "authority claim must disappear",
                },
            )
            record_variant_b(
                report_dir=report_dir,
                variant_b_text="Variant B text for tests.",
                change_declaration={
                    "changed_property": "length bound",
                    "mechanism": "bounded paragraph",
                    "declared_factors": ["length bound"],
                },
            )
            ledger = ExposureLedger(report_dir / "exposure-ledger.json")
            with self.assertRaises(WorkflowError):
                freeze_protocol(
                    report_dir=report_dir,
                    protocol=self._protocol(),
                    reserves_dir=RESERVES,
                    ledger=ledger,
                    student=STUDENT,
                )
            self._seed_terminal_development(report_dir)
            bad_budget = {**self._protocol(), "attempt_budget": 8}
            with self.assertRaises(WorkflowError):
                freeze_protocol(
                    report_dir=report_dir,
                    protocol=bad_budget,
                    reserves_dir=RESERVES,
                    ledger=ledger,
                    student=STUDENT,
                )
            string_route = {**self._protocol(), "route": "offline fixture"}
            with self.assertRaises(WorkflowError):
                freeze_protocol(
                    report_dir=report_dir,
                    protocol=string_route,
                    reserves_dir=RESERVES,
                    ledger=ledger,
                    student=STUDENT,
                )
            manifest = freeze_protocol(
                report_dir=report_dir,
                protocol=self._protocol(),
                reserves_dir=RESERVES,
                ledger=ledger,
                student=STUDENT,
            )
            bindings = manifest["bindings"]
            for key in (
                "output_schema_sha256",
                "case_family_contract_sha256",
                "validator_module_sha256",
                "development_schedule_sha256",
                "exposure_ledger_sha256",
            ):
                self.assertRegex(bindings[key], r"^[0-9a-f]{64}$")
            self.assertEqual(manifest["protocol"]["attempt_budget"], 16)
            self.assertEqual(manifest["route"]["adapter"], "offline-fixture")
            self.assertNotIn("curator_exercised", manifest)
            self.assertNotIn("curator_recovery_exercised", manifest)

    def test_development_schedule_is_four_a_then_four_b_and_b_waits(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report_dir = Path(temp)
            record_transfer_case(
                report_dir=report_dir,
                transfer_case={
                    "case_id": "transfer-approval",
                    "task": "State who approves requests.",
                    "supplied_source": "A supervisor approves requests.",
                    "provenance": "public test scenario",
                },
                perturbation={
                    "case_id": "transfer-approval-perturbed",
                    "task": "State who approves requests.",
                    "supplied_source": "A supervisor records requests.",
                    "provenance": "public test scenario",
                    "perturbation_note": "verb changed",
                    "expectation": "authority claim must disappear",
                },
            )
            dev_dir = report_dir / "development"
            cases = [
                {"case_id": "dev-one", "task": "t1", "supplied_source": "s1"},
                {"case_id": "dev-two", "task": "t2", "supplied_source": "s2"},
                {"case_id": "transfer-approval", "task": "t3", "supplied_source": "s3"},
                {"case_id": "transfer-approval-perturbed", "task": "t4", "supplied_source": "s4"},
            ]
            build_positions(
                comparison_dir=dev_dir,
                family={"family_id": "dev-common", "cases": cases},
                kind="development",
                cases=cases,
            )
            schedule = json.loads((dev_dir / "schedule.json").read_text(encoding="utf-8"))
            ordered_variants = [
                next(p["variant"] for p in schedule["positions"] if p["position_id"] == pid)
                for pid in schedule["order"]
            ]
            self.assertEqual(ordered_variants, ["a"] * 4 + ["b"] * 4)
            first_b = schedule["order"][4]
            cases_by_id = {c["case_id"]: c for c in cases}
            with self.assertRaises(WorkflowError):
                run_position(
                    comparison_dir=dev_dir,
                    schedule=schedule,
                    position_id=first_b,
                    cases_by_id=cases_by_id,
                    instructions={"a": "A", "b": "B"},
                    runner=fixture_runner,
                    adapter="offline-fixture",
                    model_id="offline-fixture",
                    recorded_by=STUDENT,
                )
            for position_id in schedule["order"][:4]:
                run_position(
                    comparison_dir=dev_dir,
                    schedule=json.loads((dev_dir / "schedule.json").read_text(encoding="utf-8")),
                    position_id=position_id,
                    cases_by_id=cases_by_id,
                    instructions={"a": "A instruction"},
                    runner=fixture_runner,
                    adapter="offline-fixture",
                    model_id="offline-fixture",
                    recorded_by=STUDENT,
                )
            with self.assertRaises(WorkflowError):
                run_position(
                    comparison_dir=dev_dir,
                    schedule=json.loads((dev_dir / "schedule.json").read_text(encoding="utf-8")),
                    position_id=first_b,
                    cases_by_id=cases_by_id,
                    instructions={"b": "B instruction"},
                    runner=fixture_runner,
                    adapter="offline-fixture",
                    model_id="offline-fixture",
                    recorded_by=STUDENT,
                )
            record_variant_b(
                report_dir=report_dir,
                variant_b_text="Variant B after A.",
                change_declaration={
                    "changed_property": "length bound",
                    "mechanism": "bounded paragraph",
                    "declared_factors": ["length bound"],
                },
            )
            result = run_position(
                comparison_dir=dev_dir,
                schedule=json.loads((dev_dir / "schedule.json").read_text(encoding="utf-8")),
                position_id=first_b,
                cases_by_id=cases_by_id,
                instructions={"b": "Variant B after A."},
                runner=fixture_runner,
                adapter="offline-fixture",
                model_id="offline-fixture",
                recorded_by=STUDENT,
            )
            self.assertEqual(result["outcome"], "returned")

    def test_resume_probe_is_single_use_and_frozen_route_is_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report_dir = Path(temp)
            self._prepare_development(report_dir)
            ledger = ExposureLedger(report_dir / "exposure-ledger.json")
            manifest = freeze_protocol(
                report_dir=report_dir,
                protocol=self._protocol(),
                reserves_dir=RESERVES,
                ledger=ledger,
                student=STUDENT,
            )
            family = select_family(
                reserves_dir=RESERVES, ledger=ledger, freeze_manifest=manifest, student=STUDENT
            )
            comparison_dir = Path(manifest["comparison_dir"])
            build_positions(comparison_dir=comparison_dir, family=family, kind="held-out")
            schedule = json.loads((comparison_dir / "schedule.json").read_text(encoding="utf-8"))
            instructions = load_frozen_instructions(comparison_dir)
            cases_by_id = {c["case_id"]: c for c in family["cases"]}

            def failing_runner(request: dict) -> str:
                raise RuntimeError("authentication failed for the route")

            run_position(
                comparison_dir=comparison_dir,
                schedule=json.loads((comparison_dir / "schedule.json").read_text(encoding="utf-8")),
                position_id=schedule["order"][0],
                cases_by_id=cases_by_id,
                instructions=instructions,
                runner=failing_runner,
                adapter="offline-fixture",
                model_id="offline-fixture",
                recorded_by=STUDENT,
            )
            with self.assertRaises(WorkflowError):
                run_position(
                    comparison_dir=comparison_dir,
                    schedule=json.loads((comparison_dir / "schedule.json").read_text(encoding="utf-8")),
                    position_id=schedule["order"][1],
                    cases_by_id=cases_by_id,
                    instructions=instructions,
                    runner=fixture_runner,
                    adapter="openrouter",
                    model_id="other-model",
                    recorded_by=STUDENT,
                    resume_probe=True,
                )
            resumed = run_position(
                comparison_dir=comparison_dir,
                schedule=json.loads((comparison_dir / "schedule.json").read_text(encoding="utf-8")),
                position_id=schedule["order"][1],
                cases_by_id=cases_by_id,
                instructions=instructions,
                runner=fixture_runner,
                adapter="offline-fixture",
                model_id="offline-fixture",
                recorded_by=STUDENT,
                resume_probe=True,
            )
            self.assertEqual(resumed["outcome"], "returned")
            later_stop = run_position(
                comparison_dir=comparison_dir,
                schedule=json.loads((comparison_dir / "schedule.json").read_text(encoding="utf-8")),
                position_id=schedule["order"][2],
                cases_by_id=cases_by_id,
                instructions=instructions,
                runner=failing_runner,
                adapter="offline-fixture",
                model_id="offline-fixture",
                recorded_by=STUDENT,
            )
            self.assertEqual(later_stop["failure_class"], "route-wide")
            with self.assertRaises(WorkflowError):
                run_position(
                    comparison_dir=comparison_dir,
                    schedule=json.loads((comparison_dir / "schedule.json").read_text(encoding="utf-8")),
                    position_id=schedule["order"][3],
                    cases_by_id=cases_by_id,
                    instructions=instructions,
                    runner=fixture_runner,
                    adapter="offline-fixture",
                    model_id="offline-fixture",
                    recorded_by=STUDENT,
                    resume_probe=True,
                )

    def test_closed_unstarted_counts_as_unstarted_and_disputes_and_latency(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report_dir = Path(temp)
            self._prepare_development(report_dir)
            ledger = ExposureLedger(report_dir / "exposure-ledger.json")
            manifest = freeze_protocol(
                report_dir=report_dir,
                protocol=self._protocol(),
                reserves_dir=RESERVES,
                ledger=ledger,
                student=STUDENT,
            )
            family = select_family(
                reserves_dir=RESERVES, ledger=ledger, freeze_manifest=manifest, student=STUDENT
            )
            comparison_dir = Path(manifest["comparison_dir"])
            build_positions(comparison_dir=comparison_dir, family=family, kind="held-out")
            schedule = json.loads((comparison_dir / "schedule.json").read_text(encoding="utf-8"))
            instructions = load_frozen_instructions(comparison_dir)
            first_id = schedule["order"][0]
            run_position(
                comparison_dir=comparison_dir,
                schedule=json.loads((comparison_dir / "schedule.json").read_text(encoding="utf-8")),
                position_id=first_id,
                cases_by_id={c["case_id"]: c for c in family["cases"]},
                instructions=instructions,
                runner=fixture_runner,
                adapter="offline-fixture",
                model_id="offline-fixture",
                recorded_by=STUDENT,
            )
            close_unstarted_positions(
                comparison_dir=comparison_dir, reason="stopped after one returned position", student=STUDENT
            )
            index = build_blinded_index(comparison_dir=comparison_dir, family=family)
            self.assertEqual(len(index["entries"]), 1)
            record_assessment(
                comparison_dir=comparison_dir,
                blind_id=index["entries"][0]["blind_id"],
                assessment={
                    "category": index["entries"][0]["expected_category"],
                    "source_pointer": "supplied source",
                    "rationale": "test rationale",
                },
            )
            record_dispute(
                comparison_dir=comparison_dir,
                blind_id=index["entries"][0]["blind_id"],
                reason="human-reference disagreement",
                student=STUDENT,
            )
            aggregate = aggregate_lab03(comparison_dir=comparison_dir)
            started = aggregate["nested_counts"]["a"]["started"] + aggregate["nested_counts"]["b"]["started"]
            unstarted = aggregate["nested_counts"]["a"]["unstarted"] + aggregate["nested_counts"]["b"]["unstarted"]
            self.assertEqual(started, 1)
            self.assertEqual(unstarted, 15)
            self.assertEqual(aggregate["disputed_blind_ids"], [index["entries"][0]["blind_id"]])
            assessable = (
                aggregate["nested_counts"]["a"]["assessable"]
                + aggregate["nested_counts"]["b"]["assessable"]
            )
            self.assertEqual(assessable, 0)
            self.assertEqual(aggregate["unknown_values"]["quota_usage"], "unknown")
            latencies = aggregate["observed_latency"]["a"] + aggregate["observed_latency"]["b"]
            self.assertEqual(len(latencies), 1)
            self.assertIsInstance(latencies[0]["seconds"], float)

    def test_recommendation_requires_coverage_and_forces_seek_more_on_amendment(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report_dir = Path(temp)
            self._prepare_development(report_dir)
            ledger = ExposureLedger(report_dir / "exposure-ledger.json")
            manifest = freeze_protocol(
                report_dir=report_dir,
                protocol=self._protocol(),
                reserves_dir=RESERVES,
                ledger=ledger,
                student=STUDENT,
            )
            family = select_family(
                reserves_dir=RESERVES, ledger=ledger, freeze_manifest=manifest, student=STUDENT
            )
            comparison_dir = Path(manifest["comparison_dir"])
            build_positions(comparison_dir=comparison_dir, family=family, kind="held-out")
            schedule = json.loads((comparison_dir / "schedule.json").read_text(encoding="utf-8"))
            instructions = load_frozen_instructions(comparison_dir)
            cases_by_id = {c["case_id"]: c for c in family["cases"]}
            for position_id in schedule["order"]:
                run_position(
                    comparison_dir=comparison_dir,
                    schedule=json.loads((comparison_dir / "schedule.json").read_text(encoding="utf-8")),
                    position_id=position_id,
                    cases_by_id=cases_by_id,
                    instructions=instructions,
                    runner=fixture_runner,
                    adapter="offline-fixture",
                    model_id="offline-fixture",
                    recorded_by=STUDENT,
                )
            index = build_blinded_index(comparison_dir=comparison_dir, family=family)
            with self.assertRaises(WorkflowError):
                record_recommendation(
                    comparison_dir=comparison_dir,
                    outcome="retain-a",
                    rationale="too early",
                    limitations=["offline fixture"],
                    student=STUDENT,
                )
            for entry in index["entries"]:
                record_assessment(
                    comparison_dir=comparison_dir,
                    blind_id=entry["blind_id"],
                    assessment={
                        "category": entry["expected_category"],
                        "source_pointer": "supplied source",
                        "rationale": "test rationale",
                    },
                )
            aggregate_lab03(comparison_dir=comparison_dir)
            amendment_dir = comparison_dir / "scoring" / "evaluator-amendments" / "amend-1"
            amendment_dir.mkdir(parents=True)
            (amendment_dir / "diagnostic.json").write_text("{\"defect\": \"reference\"}\n", encoding="utf-8")
            with self.assertRaises(WorkflowError):
                record_recommendation(
                    comparison_dir=comparison_dir,
                    outcome="retain-a",
                    rationale="amendment present",
                    limitations=["offline fixture"],
                    student=STUDENT,
                )
            path = record_recommendation(
                comparison_dir=comparison_dir,
                outcome="seek-more-evidence",
                rationale="evaluator amendment requires more evidence",
                limitations=["offline fixture", "evaluator amendment"],
                student=STUDENT,
            )
            recorded = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.assertEqual(recorded["protocol_freeze_id"], manifest["freeze_id"])
            self.assertEqual(recorded["blocking_failures"], self._protocol()["blocking_failures"])

    def test_cli_exposes_premature_exposure_and_dispute_commands(self) -> None:
        parser = _build_parser()
        commands = {action.dest: action for action in parser._subparsers._group_actions}
        lab03 = commands["command"].choices["lab03"]
        lab03_commands = {
            action.dest: {choice: subparser for choice, subparser in action.choices.items()}
            for action in lab03._subparsers._group_actions
        }["lab03_command"]
        self.assertIn("record-premature-exposure", lab03_commands)
        self.assertIn("record-dispute", lab03_commands)
        self.assertIn("curator-prepare", lab03_commands)
        self.assertIn("curator-ingest", lab03_commands)
        self.assertIn("curator-review", lab03_commands)
        self.assertIn("record-interrupted", lab03_commands)
        self.assertIn("dev-record-interrupted", lab03_commands)
        self.assertIn("curator-attempt-failed", lab03_commands)
        self.assertIn("record-amendment", lab03_commands)
        self.assertIn("record-completion", lab03_commands)

    def test_evaluator_amendment_is_append_only_and_forces_seek_more(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            comparison_dir = Path(temp)
            path = record_evaluator_amendment(
                comparison_dir=comparison_dir,
                amendment_id="amend-ref-1",
                defect="reference omits approval authority",
                confirmed_by=STUDENT,
            )
            recorded = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.assertEqual(recorded["amendment_id"], "amend-ref-1")
            self.assertEqual(recorded["confirmed_by"], STUDENT)
            with self.assertRaises(WorkflowError):
                record_evaluator_amendment(
                    comparison_dir=comparison_dir,
                    amendment_id="amend-ref-1",
                    defect="overwrite attempt",
                    confirmed_by=STUDENT,
                )

    def test_dispatched_interruption_becomes_a_non_retryable_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            comparison_dir = Path(temp)
            position_id = "pos-case-a-1"
            (comparison_dir / "schedule.json").write_text(
                json.dumps({
                    "kind": "held-out",
                    "order": [position_id],
                    "positions": [{
                        "position_id": position_id,
                        "case_id": "case",
                        "variant": "a",
                        "attempt": 1,
                        "state": "unstarted",
                    }],
                }),
                encoding="utf-8",
            )
            attempt_dir = comparison_dir / "attempts" / position_id
            attempt_dir.mkdir(parents=True)
            (attempt_dir / "request.json").write_text("{}\n", encoding="utf-8")
            record_interrupted_position(
                comparison_dir=comparison_dir,
                position_id=position_id,
                reason="process ended after dispatch",
                student=STUDENT,
            )
            schedule = json.loads((comparison_dir / "schedule.json").read_text(encoding="utf-8"))
            self.assertEqual(schedule["positions"][0]["state"], "failed")
            error = json.loads((attempt_dir / "error.json").read_text(encoding="utf-8"))
            self.assertTrue(error["interrupted_after_dispatch"])
            with self.assertRaises(WorkflowError):
                record_interrupted_position(
                    comparison_dir=comparison_dir,
                    position_id=position_id,
                    reason="repeat",
                    student=STUDENT,
                )


if __name__ == "__main__":
    unittest.main()
