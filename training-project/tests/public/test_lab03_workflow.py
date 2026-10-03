import json
import subprocess
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
    eligible_families,
    freeze_protocol,
    load_family,
    load_frozen_instructions,
    record_assessment,
    record_completion_status,
    record_recommendation,
    record_regression,
    record_interrupted_position,
    record_selected_comparison,
    record_variant_b,
    run_position,
    select_family,
    start_calibration,
    structural_check,
    submit_calibration,
    verify_lab03,
)
from learning_project.lab03_adapters import cases_for, instructions_for
from learning_project.workflow import WorkflowError

TRAINING_PROJECT = Path(__file__).resolve().parent.parent.parent
CASES = TRAINING_PROJECT / "cases" / "lab03"
RESERVES = CASES / "reserves"
INSTRUCTIONS = TRAINING_PROJECT / "instructions" / "lab03"
CALIBRATION = CASES / "calibration"
AUTHORED_FAILURE = CASES / "authored-failure" / "authored-failure.json"

STUDENT = "student-01"
REPORT_SCREENSHOTS = (
    "01-calibration.png",
    "02-development.png",
    "03-freeze.png",
    "04-held-out-execution.png",
    "05-scoring-recommendation.png",
    "06-regression.png",
    "07-final-verification.png",
)


def report_markdown(*, partial: bool) -> str:
    status = "Completion status: honest-partial." if partial else "Complete laboratory report."
    screenshot_names = (REPORT_SCREENSHOTS[-1],) if partial else REPORT_SCREENSHOTS
    links = "\n".join(f"![evidence](screenshots/{name})" for name in screenshot_names)
    return f"# Report\n\n{status}\n\n{links}\n"


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

    def test_curator_generated_family_is_not_supported(self) -> None:
        family = load_family(RESERVES / "reserve-criteria-chain" / "family.json")
        family["origin"] = "curator-generated"
        family["provenance"] = {"curator_session": "legacy", "inputs_sha256": "0" * 64}
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "legacy-curator-family.json"
            path.write_text(json.dumps(family), encoding="utf-8")
            with self.assertRaisesRegex(WorkflowError, "origin is not supported"):
                load_family(path)

    def test_development_case_lookup_uses_only_course_owned_cases(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            development_dir = Path(temp)
            (development_dir / "schedule.json").write_text(
                json.dumps({"kind": "development"}), encoding="utf-8"
            )
            cases = cases_for(development_dir, TRAINING_PROJECT, Path(temp))
        self.assertEqual(
            set(cases),
            {"dev-source-baseline-definition", "dev-approval-authority-absent"},
        )

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
    def _write_report_evidence(self, report_dir: Path, *, partial: bool) -> None:
        (report_dir / "REPORT.md").write_text(report_markdown(partial=partial), encoding="utf-8")
        if not partial:
            screenshot_dir = report_dir / "screenshots"
            screenshot_dir.mkdir(parents=True, exist_ok=True)
            for screenshot_name in REPORT_SCREENSHOTS[:6]:
                (screenshot_dir / screenshot_name).write_bytes(b"committed screenshot fixture")

    def _commit_report(self, report_dir: Path) -> str:
        subprocess.run(["git", "init", "-q", str(report_dir)], check=True)
        subprocess.run(["git", "-C", str(report_dir), "config", "user.name", "Test Student"], check=True)
        subprocess.run(
            ["git", "-C", str(report_dir), "config", "user.email", "student@example.invalid"],
            check=True,
        )
        subprocess.run(["git", "-C", str(report_dir), "add", "."], check=True)
        subprocess.run(["git", "-C", str(report_dir), "commit", "-q", "-m", "final evidence"], check=True)
        return subprocess.run(
            ["git", "-C", str(report_dir), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

    def _prepare_development(self, report_dir: Path) -> None:
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
        case_ids = ["dev-criteria", "dev-authority"]
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
            self._write_report_evidence(report_dir, partial=False)
            record_completion_status(
                report_dir=report_dir,
                status="complete",
                detail={
                    "stopped_at_step": "Step 15",
                    "limitation": "none",
                    "preserved_evidence": "reports/lab03/",
                    "recorded_by": STUDENT,
                },
            )
            final_commit = self._commit_report(report_dir)
            verification = verify_lab03(report_dir=report_dir, final_commit=final_commit)
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
            self._write_report_evidence(report_dir, partial=True)
            record_completion_status(
                report_dir=report_dir,
                status="honest-partial",
                detail={
                    "stopped_at_step": "Step 9",
                    "limitation": "route unavailable",
                    "preserved_evidence": "reports/lab03/comparisons/",
                    "recorded_by": STUDENT,
                },
            )
            final_commit = self._commit_report(report_dir)
            verification = verify_lab03(report_dir=report_dir, final_commit=final_commit)
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

    def test_freeze_stops_when_no_eligible_family_remains(self) -> None:
        from learning_project.lab03 import record_premature_exposure

        with tempfile.TemporaryDirectory() as temp:
            report_dir = Path(temp)
            self._prepare_development(report_dir)
            ledger = ExposureLedger(report_dir / "exposure-ledger.json")
            for family_id in eligible_families(RESERVES, ledger, freeze_at=None):
                record_premature_exposure(ledger=ledger, family_id=family_id, student=STUDENT)
            protocol = {**self._protocol(), "curator_recovery": True}
            with self.assertRaisesRegex(WorkflowError, "No eligible reserve family remains"):
                freeze_protocol(
                    report_dir=report_dir,
                    protocol=protocol,
                    reserves_dir=RESERVES,
                    ledger=ledger,
                    student=STUDENT,
                )

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

    def test_development_schedule_is_two_a_then_two_b_and_b_waits(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report_dir = Path(temp)
            dev_dir = report_dir / "development"
            cases = [
                {"case_id": "dev-one", "task": "t1", "supplied_source": "s1"},
                {"case_id": "dev-two", "task": "t2", "supplied_source": "s2"},
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
            self.assertEqual(ordered_variants, ["a"] * 2 + ["b"] * 2)
            first_b = schedule["order"][2]
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
            for position_id in schedule["order"][:2]:
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

    def test_closed_unstarted_counts_and_latency(self) -> None:
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
            aggregate = aggregate_lab03(comparison_dir=comparison_dir)
            expected_count_keys = {
                "attempted", "returned", "structurally_valid", "assessable", "rubric_acceptable"
            }
            self.assertEqual(set(aggregate["nested_counts"]["a"]), expected_count_keys)
            self.assertEqual(set(aggregate["nested_counts"]["b"]), expected_count_keys)
            attempted = (
                aggregate["nested_counts"]["a"]["attempted"]
                + aggregate["nested_counts"]["b"]["attempted"]
            )
            unstarted = aggregate["unstarted_counts"]["a"] + aggregate["unstarted_counts"]["b"]
            self.assertEqual(attempted, 1)
            self.assertEqual(unstarted, 15)
            self.assertNotIn("disputed_blind_ids", aggregate)
            self.assertNotIn("corrected_blind_ids", aggregate)
            assessable = (
                aggregate["nested_counts"]["a"]["assessable"]
                + aggregate["nested_counts"]["b"]["assessable"]
            )
            self.assertEqual(assessable, 1)
            self.assertNotIn("resolved_model_comparability", aggregate)
            self.assertEqual(aggregate["unknown_values"]["quota_usage"], "unknown")
            latencies = aggregate["observed_latency"]["a"] + aggregate["observed_latency"]["b"]
            self.assertEqual(len(latencies), 1)
            self.assertIsInstance(latencies[0]["seconds"], float)

    def test_recommendation_requires_coverage_and_uses_one_of_four_outcomes(self) -> None:
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
            path = record_recommendation(
                comparison_dir=comparison_dir,
                outcome="retain-a",
                rationale="Variant B did not improve the frozen criteria.",
                limitations=["offline fixture"],
                student=STUDENT,
            )
            recorded = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.assertEqual(recorded["outcome"], "retain-a")
            self.assertEqual(recorded["protocol_freeze_id"], manifest["freeze_id"])
            self.assertEqual(recorded["blocking_failures"], self._protocol()["blocking_failures"])

    def test_cli_exposes_core_workflow_without_curator_or_dispute_commands(self) -> None:
        parser = _build_parser()
        commands = {action.dest: action for action in parser._subparsers._group_actions}
        lab03 = commands["command"].choices["lab03"]
        lab03_commands = {
            action.dest: {choice: subparser for choice, subparser in action.choices.items()}
            for action in lab03._subparsers._group_actions
        }["lab03_command"]
        self.assertIn("record-premature-exposure", lab03_commands)
        self.assertIn("record-interrupted", lab03_commands)
        self.assertIn("dev-record-interrupted", lab03_commands)
        self.assertIn("record-completion", lab03_commands)
        for removed_command in (
            "record-transfer",
            "curator-prepare",
            "curator-launch",
            "curator-ingest",
            "curator-attempt-failed",
            "curator-review",
            "record-dispute",
            "record-amendment",
            "record-correction",
        ):
            self.assertNotIn(removed_command, lab03_commands)


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

class Lab03Gate2RemediationTests(unittest.TestCase):
    """Coverage for the eight confirmed Gate 2 blockers reopened on 2026-09-30."""

    def _prepare_development(self, report_dir: Path) -> None:
        record_variant_b(
            report_dir=report_dir,
            variant_b_text="Variant B text for tests.",
            change_declaration={
                "changed_property": "length bound",
                "mechanism": "bounded paragraph",
                "declared_factors": ["length bound"],
            },
        )
        Lab03WorkflowTests._seed_terminal_development(self, report_dir)  # type: ignore[arg-type]

    def _protocol(self) -> dict:
        return Lab03WorkflowTests._protocol(self)  # type: ignore[arg-type]

    def _development_schedule(self, a_states, b_states=("unstarted",) * 2):
        positions = []
        case_ids = ["dev-criteria", "dev-authority"]
        for case_id, a_state in zip(case_ids, a_states):
            positions.append({"position_id": f"pos-{case_id}-a-1", "case_id": case_id,
                              "case_index": 0, "variant": "a", "attempt": 1, "state": a_state})
        for case_id, b_state in zip(case_ids, b_states):
            positions.append({"position_id": f"pos-{case_id}-b-1", "case_id": case_id,
                              "case_index": 0, "variant": "b", "attempt": 1, "state": b_state})
        order = [p["position_id"] for p in positions]
        return {"kind": "development", "family_id": "dev-common", "order": order, "positions": positions}

    def test_all_failed_variant_a_blocks_variant_b_and_requires_partial_stop(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            comparison_dir = Path(temp)
            schedule = self._development_schedule(("failed",) * 2)
            (comparison_dir / "variant-b.txt").write_text("Variant B text.", encoding="utf-8")
            with self.assertRaises(WorkflowError) as ctx:
                run_position(
                    comparison_dir=comparison_dir,
                    schedule=schedule,
                    position_id="pos-dev-criteria-b-1",
                    cases_by_id={"dev-criteria": {"case_id": "dev-criteria", "task": "t", "supplied_source": "s"}},
                    instructions={"b": "instruction"},
                    runner=fixture_runner,
                    adapter="offline-fixture",
                    model_id="offline-fixture",
                    recorded_by=STUDENT,
                )
            self.assertIn("honest-partial", str(ctx.exception))

    def test_completion_detail_contract_is_enforced(self) -> None:
        from learning_project.lab03 import validate_completion_detail
        with tempfile.TemporaryDirectory() as temp:
            report_dir = Path(temp)
            good = {"stopped_at_step": "Step 4", "limitation": "route unavailable",
                    "preserved_evidence": "reports/lab03/development/"}
            checked = validate_completion_detail(good)
            self.assertEqual(checked["stopped_at_step"], "Step 4")
            record_completion_status(report_dir=report_dir, status="honest-partial",
                                     detail={**good, "recorded_by": STUDENT})
            status = yaml.safe_load((report_dir / "completion-status.yaml").read_text(encoding="utf-8"))
            self.assertEqual(status["status"], "honest-partial")
            for bad in ({}, {"stopped_at_step": "Step 4"}, {**good, "extra": 1}):
                with self.assertRaises(WorkflowError):
                    validate_completion_detail(bad)

    def test_resumed_completion_supersedes_status_append_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report_dir = Path(temp)
            detail = {"stopped_at_step": "Step 4", "limitation": "route unavailable",
                      "preserved_evidence": "reports/lab03/development/"}
            record_completion_status(report_dir=report_dir, status="honest-partial",
                                     detail={**detail, "recorded_by": STUDENT})
            resume_detail = {"stopped_at_step": "Step 13", "limitation": "none; resumed run completed",
                             "preserved_evidence": "reports/lab03/comparisons/"}
            record_completion_status(report_dir=report_dir, status="complete",
                                     detail={**resume_detail, "recorded_by": STUDENT})
            events = yaml.safe_load((report_dir / "completion-events.yaml").read_text(encoding="utf-8"))
            self.assertEqual(len(events["events"]), 2)
            self.assertEqual(events["events"][0]["status"], "honest-partial")
            self.assertEqual(events["events"][1]["status"], "complete")
            status = yaml.safe_load((report_dir / "completion-status.yaml").read_text(encoding="utf-8"))
            self.assertEqual(status["status"], "complete")
            self.assertEqual(status["event_count"], 2)

    def test_verifier_rejects_an_unresolvable_final_commit(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report_dir = Path(temp)
            detail = {
                "stopped_at_step": "Step 4",
                "limitation": "route unavailable",
                "preserved_evidence": "reports/lab03/development/",
            }
            record_completion_status(
                report_dir=report_dir,
                status="honest-partial",
                detail={**detail, "recorded_by": STUDENT},
            )
            (report_dir / "REPORT.md").write_text("Partial completion report.\n", encoding="utf-8")

            verification = verify_lab03(report_dir=report_dir, final_commit="a" * 40)

            self.assertEqual(verification["outcome"], "failed")
            commit_check = next(
                item for item in verification["checks"] if item["check_id"] == "final-commit"
            )
            self.assertEqual(commit_check["status"], "failed")

    def test_verifier_rejects_report_evidence_changed_after_final_commit(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            report_dir = root / "training-project" / "reports" / "lab03"
            report_dir.mkdir(parents=True)
            detail = {
                "stopped_at_step": "Step 4",
                "limitation": "route unavailable",
                "preserved_evidence": "reports/lab03/development/",
            }
            record_completion_status(
                report_dir=report_dir,
                status="honest-partial",
                detail={**detail, "recorded_by": STUDENT},
            )
            report = report_dir / "REPORT.md"
            report.write_text("Partial completion report.\n", encoding="utf-8")
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Test Student"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "student@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(root), "add", "."], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", "final evidence"], check=True)
            final_commit = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            report.write_text("Partial completion report changed after commit.\n", encoding="utf-8")

            verification = verify_lab03(report_dir=report_dir, final_commit=final_commit)

            self.assertEqual(verification["outcome"], "failed")
            commit_check = next(
                item for item in verification["checks"] if item["check_id"] == "final-commit"
            )
            self.assertEqual(commit_check["status"], "failed")
            self.assertIn("changed after", commit_check["message"])

    def test_verifier_allows_only_declared_post_commit_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            report_dir = root / "training-project" / "reports" / "lab03"
            report_dir.mkdir(parents=True)
            detail = {
                "stopped_at_step": "Step 4",
                "limitation": "route unavailable",
                "preserved_evidence": "reports/lab03/development/",
            }
            record_completion_status(
                report_dir=report_dir,
                status="honest-partial",
                detail={**detail, "recorded_by": STUDENT},
            )
            (report_dir / "REPORT.md").write_text(report_markdown(partial=True), encoding="utf-8")
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Test Student"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "student@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(root), "add", "."], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", "final evidence"], check=True)
            final_commit = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            screenshot = report_dir / "screenshots" / "07-final-verification.png"
            screenshot.parent.mkdir()
            screenshot.write_bytes(b"post-commit screenshot")
            submission = report_dir / "submission" / "REPORT.md"
            submission.parent.mkdir()
            submission.write_text("post-commit Teams copy\n", encoding="utf-8")

            verification = verify_lab03(report_dir=report_dir, final_commit=final_commit)

            self.assertEqual(verification["outcome"], "passed-partial")
            self.assertTrue((report_dir / "verification-report.json").exists())

    def test_verifier_rejects_an_ancestor_instead_of_branch_head(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            report_dir = root / "training-project" / "reports" / "lab03"
            report_dir.mkdir(parents=True)
            detail = {
                "stopped_at_step": "Step 4",
                "limitation": "route unavailable",
                "preserved_evidence": "reports/lab03/development/",
            }
            record_completion_status(
                report_dir=report_dir,
                status="honest-partial",
                detail={**detail, "recorded_by": STUDENT},
            )
            (report_dir / "REPORT.md").write_text("Partial completion report.\n", encoding="utf-8")
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Test Student"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "student@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(root), "add", "."], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", "evidence"], check=True)
            ancestor = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
            ).stdout.strip()
            (root / "unrelated.txt").write_text("later commit\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "unrelated.txt"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", "later"], check=True)

            verification = verify_lab03(report_dir=report_dir, final_commit=ancestor)

            self.assertEqual(verification["outcome"], "failed")
            commit_check = next(
                item for item in verification["checks"] if item["check_id"] == "final-commit"
            )
            self.assertIn("current branch head", commit_check["message"])

    def test_complete_verifier_requires_six_committed_screenshots_and_seven_report_links(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            report_dir = root / "training-project" / "reports" / "lab03"
            report_dir.mkdir(parents=True)
            record_completion_status(
                report_dir=report_dir,
                status="complete",
                detail={
                    "stopped_at_step": "Step 15",
                    "limitation": "none",
                    "preserved_evidence": "reports/lab03/",
                    "recorded_by": STUDENT,
                },
            )
            (report_dir / "REPORT.md").write_text("# Report\n", encoding="utf-8")
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Test Student"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "student@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(root), "add", "."], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", "incomplete report"], check=True)
            final_commit = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
            ).stdout.strip()

            verification = verify_lab03(report_dir=report_dir, final_commit=final_commit)

            report_check = next(item for item in verification["checks"] if item["check_id"] == "report")
            self.assertEqual(report_check["status"], "failed")
            self.assertIn("01-calibration.png", report_check["message"])

    def test_post_freeze_premature_exposure_removes_eligibility(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            ledger = ExposureLedger(Path(temp) / "exposure-ledger.json")
            families = sorted(p.parent.name for p in RESERVES.glob("*/family.json"))
            ledger.append({"event": "premature-exposure", "family_id": families[0],
                           "actor": STUDENT, "recorded_at": "2100-01-01T00:00:00+00:00"})
            eligible = eligible_families(RESERVES, ledger, freeze_at="2000-01-01T00:00:00+00:00")
            self.assertNotIn(families[0], eligible)
            self.assertTrue(eligible, "remaining families must stay eligible")

    def test_runner_result_records_observed_model_without_changing_frozen_route(self) -> None:
        from learning_project.lab03_adapters import RunnerResult
        with tempfile.TemporaryDirectory() as temp:
            comparison_dir = Path(temp)
            position_id = "pos-case-a-1"
            (comparison_dir / "schedule.json").write_text(json.dumps({
                "kind": "held-out", "order": [position_id],
                "positions": [{"position_id": position_id, "case_id": "case", "variant": "a",
                               "attempt": 1, "state": "unstarted"}],
            }), encoding="utf-8")

            def live_runner(request: dict) -> RunnerResult:
                return RunnerResult(content=json.dumps(
                    {"case_id": request["case_id"], "proposed_text": "answer"}), observed_model="provider/x")

            result = run_position(
                comparison_dir=comparison_dir, schedule=json.loads(
                    (comparison_dir / "schedule.json").read_text(encoding="utf-8")),
                position_id=position_id,
                cases_by_id={"case": {"case_id": "case", "task": "t", "supplied_source": "s"}},
                instructions={"a": "instruction"}, runner=live_runner,
                adapter="openrouter", model_id="openrouter/free", recorded_by=STUDENT,
            )
            self.assertEqual(result["outcome"], "returned")
            metadata = json.loads(
                (comparison_dir / "attempts" / position_id / "run-metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["observed_model"], "provider/x")
            self.assertEqual(metadata["model_id"], "openrouter/free")


    def test_status_reports_resume_bootstrap_fields(self) -> None:
        from learning_project.lab03 import lab03_status
        with tempfile.TemporaryDirectory() as temp:
            report_dir = Path(temp)
            summary = lab03_status(report_dir=report_dir)
            self.assertEqual(summary["comparisons"], [])
            comparison_dir = report_dir / "comparisons" / "cmp-x"
            comparison_dir.mkdir(parents=True)
            (comparison_dir / "freeze-manifest.json").write_text(json.dumps({
                "freeze_id": "cmp-x", "frozen_at": "2026-09-30T10:00:00+00:00",
                "resume_window": "48h", "route": {"adapter": "openrouter", "model_id": "openrouter/free"},
            }), encoding="utf-8")
            (comparison_dir / "schedule.json").write_text(json.dumps({
                "kind": "held-out", "order": ["p1", "p2"],
                "positions": [{"position_id": "p1", "state": "returned"},
                              {"position_id": "p2", "state": "unstarted"}],
            }), encoding="utf-8")
            summary = lab03_status(report_dir=report_dir)
            entry = summary["comparisons"][0]
            self.assertEqual(entry["comparison_id"], "cmp-x")
            self.assertEqual(entry["position_counts"], {"returned": 1, "unstarted": 1})
            self.assertEqual(entry["next_unstarted_position"], "p2")
            self.assertEqual(entry["resume_window"], "48h")
            self.assertIn("resume_deadline", entry)


    def _prepare_completion_ready_comparison(self, report_dir: Path) -> None:
        """Freeze and complete a minimal sixteen-position comparison offline."""
        self._prepare_development(report_dir)
        ledger = ExposureLedger(report_dir / "exposure-ledger.json")
        manifest = freeze_protocol(
            report_dir=report_dir, protocol=self._protocol(),
            reserves_dir=RESERVES, ledger=ledger, student=STUDENT,
        )
        family = select_family(
            reserves_dir=RESERVES, ledger=ledger, freeze_manifest=manifest, student=STUDENT,
        )
        comparison_dir = Path(manifest["comparison_dir"])
        build_positions(comparison_dir=comparison_dir, family=family, kind="held-out")
        schedule = json.loads((comparison_dir / "schedule.json").read_text(encoding="utf-8"))
        cases_by_id = {c["case_id"]: c for c in family["cases"]}
        instructions = load_frozen_instructions(comparison_dir)
        for position_id in schedule["order"]:
            run_position(
                comparison_dir=comparison_dir, schedule=schedule, position_id=position_id,
                cases_by_id=cases_by_id, instructions=instructions, runner=fixture_runner,
                adapter="offline-fixture", model_id="offline-fixture", recorded_by=STUDENT,
            )
        revealed = json.loads((comparison_dir / "revealed-family.json").read_text(encoding="utf-8"))
        build_blinded_index(comparison_dir=comparison_dir, family=revealed["family"])


if __name__ == "__main__":
    unittest.main()