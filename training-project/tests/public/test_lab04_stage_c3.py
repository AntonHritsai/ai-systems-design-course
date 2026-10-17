"""Laboratory 04 Stage C3 evaluation tests: judgments, metrics, evidence, decision."""
import json
import os
import tempfile
import unittest
from pathlib import Path

from learning_project import lab04_index, lab04_retrieval, lab04_evaluation
from learning_project.cli import main
from learning_project.workflow import WorkflowError

try:
    from .test_lab04_stage_c2 import Encoder, setup
except ImportError:
    from test_lab04_stage_c2 import Encoder, setup
CASES = Path(__file__).resolve().parents[2] / "cases" / "lab04"


def judged(report, tmp):
    path = Path(tmp) / "judgments.json"
    path.write_text(json.dumps({
        "Evaluation Case A": [{
            "stable retrieval identifier": "F-B",
            "relevance judgment": "not relevant",
            "rationale": "F-B identifies the model rather than the supporting passage; it does not explain the originating record, record version, or exact location of the supporting passage."}],
        "Evaluation Case B": [{
            "stable retrieval identifier": "F-B",
            "relevance judgment": "not relevant",
            "rationale": "F-B records the source and version of the model, not of the supporting passage; the relevance judging basis is not satisfied."}]}))
    return path


class FixtureTests(unittest.TestCase):
    def test_fixture_binds_expected_results_and_records_approving_evaluator(self):
        fixture = json.loads((CASES / "stage-c3-fixture.json").read_text())
        self.assertEqual(fixture["schema_version"], "1.0")
        binding = fixture["expected-result chunking configuration binding"]
        self.assertEqual(binding["chunking configuration"], "sentence-pair-v1")
        self.assertIn("sentence-pair-v1", binding["binding rule"])
        self.assertEqual(fixture["cases source"], "stage-b-fixture.json evaluation_cases operation_input only")
        cases = fixture["evaluation_cases"]
        self.assertEqual([c["evaluation_case_id"] for c in cases], ["Evaluation Case A", "Evaluation Case B"])
        for case in cases:
            self.assertEqual(case["case_version"], 1)
            self.assertTrue(case["relevance judging basis"].strip())
            self.assertEqual(case["evaluator-only expected result"], ["F-A"])
            self.assertTrue(case["approving designated human evaluator"].strip())
            self.assertTrue(case["expected result provenance"].strip())


class JudgmentTests(unittest.TestCase):
    def test_records_relevance_judgments_for_every_returned_unit_and_refuses_short_sets(self):
        with tempfile.TemporaryDirectory() as tmp:
            report, c1 = setup(Path(tmp))
            for case in ("Evaluation Case A", "Evaluation Case B"):
                for configuration in json.loads((CASES / "stage-b-fixture.json").read_text())["retrieval_contract"]["compared retrieval configurations"]:
                    lab04_retrieval.execute_retrieval(report_dir=report, c1_fixture_path=c1, case_id=case,
                        configuration_id=configuration, encoder=Encoder())
            complete = Path(tmp) / "judgments.json"
            complete.write_text(json.dumps({
                "Evaluation Case A": [{"stable retrieval identifier": "F-A", "relevance judgment": "relevant",
                    "rationale": "F-A states the originating record identifier, record version, and exact sentence span, satisfying the relevance judging basis."}],
                "Evaluation Case B": [
                    {"stable retrieval identifier": "F-B", "relevance judgment": "not relevant",
                     "rationale": "F-B records the source and version of the model, not of the supporting passage."}]}))
            path = lab04_evaluation.record_relevance_judgments(report_dir=report,
                c3_fixture_path=CASES / "stage-c3-fixture.json", judgments_path=complete, evaluator="student tester")
            data = json.loads(path.read_text())
            self.assertEqual(data["schema_version"], "1.0")
            self.assertEqual(data["designated human evaluator"], "student tester")
            self.assertEqual(data["observation boundary"], "relevance judgments over returned retrieval units; no retrieval metric")
            by_case = {entry["evaluation case"]: entry for entry in data["judged evaluation cases"]}
            self.assertEqual(set(by_case), {"Evaluation Case A", "Evaluation Case B"})
            self.assertEqual(by_case["Evaluation Case A"]["relevance judging basis"],
                             json.loads((CASES / "stage-c3-fixture.json").read_text())["evaluation_cases"][0]["relevance judging basis"])
            self.assertEqual([j["stable retrieval identifier"] for j in by_case["Evaluation Case A"]["relevance judgments"]], ["F-A"])
            self.assertEqual([j["stable retrieval identifier"] for j in by_case["Evaluation Case B"]["relevance judgments"]], ["F-B"])
            self.assertNotIn("text query", json.dumps(data))
            short = Path(tmp) / "short.json"
            short.write_text(json.dumps({"Evaluation Case A": json.loads(complete.read_text())["Evaluation Case A"],
                                          "Evaluation Case B": []}))
            with self.assertRaises(WorkflowError):
                lab04_evaluation.record_relevance_judgments(report_dir=report,
                    c3_fixture_path=CASES / "stage-c3-fixture.json", judgments_path=short, evaluator="student tester")


class MetricTests(unittest.TestCase):
    def _prepared(self, tmp):
        report, c1 = setup(Path(tmp))
        for case in ("Evaluation Case A", "Evaluation Case B"):
            for configuration in json.loads((CASES / "stage-b-fixture.json").read_text())["retrieval_contract"]["compared retrieval configurations"]:
                lab04_retrieval.execute_retrieval(report_dir=report, c1_fixture_path=c1, case_id=case,
                    configuration_id=configuration, encoder=Encoder())
        judgments = Path(tmp) / "judgments.json"
        judgments.write_text(json.dumps({
            "Evaluation Case A": [{"stable retrieval identifier": "F-A", "relevance judgment": "relevant",
                "rationale": "F-A states the originating record identifier, record version, and exact sentence span, satisfying the relevance judging basis."}],
            "Evaluation Case B": [{"stable retrieval identifier": "F-B", "relevance judgment": "not relevant",
                "rationale": "F-B records the source and version of the model, not of the supporting passage."}]}))
        lab04_evaluation.record_relevance_judgments(report_dir=report,
            c3_fixture_path=CASES / "stage-c3-fixture.json", judgments_path=judgments, evaluator="student tester")
        return report, c1

    def test_metrics_carry_explicit_numerators_denominators_and_undefined_precision(self):
        with tempfile.TemporaryDirectory() as tmp:
            report, c1 = self._prepared(tmp)
            path = lab04_evaluation.compute_retrieval_metrics(report_dir=report,
                c3_fixture_path=CASES / "stage-c3-fixture.json", c1_fixture_path=c1, encoder=Encoder())
            data = json.loads(path.read_text())
            self.assertEqual(data["configured result count k"], 1)
            self.assertIn("sentence-pair-v1", data["expected-result chunking configuration binding"])
            self.assertNotIn("text query", json.dumps(data))
            per_case = {(entry["retrieval configuration"], entry["evaluation case"]): entry
                        for entry in data["per-case metrics"]}
            self.assertEqual(len(per_case), 8)
            lexical_a = per_case[("lexical retrieval", "Evaluation Case A")]
            self.assertEqual(lexical_a["ranked candidate output"], [])
            self.assertEqual(lexical_a["precision@1"]["numerator"], 0)
            self.assertEqual(lexical_a["precision@1"]["denominator"], 0)
            self.assertEqual(lexical_a["precision@1"]["value"], "undefined")
            self.assertIn("no returned retrieval unit", lexical_a["precision@1"]["reason"])
            self.assertEqual(lexical_a["recall@1"]["numerator"], 0)
            self.assertEqual(lexical_a["recall@1"]["denominator"], 1)
            self.assertEqual(lexical_a["recall@1"]["value"], 0.0)
            embedding_a = per_case[("embedding-based retrieval", "Evaluation Case A")]
            self.assertEqual(embedding_a["precision@1"]["value"], 1.0)
            self.assertEqual(embedding_a["recall@1"]["value"], 1.0)
            embedding_b = per_case[("embedding-based retrieval", "Evaluation Case B")]
            self.assertEqual(embedding_b["precision@1"]["value"], 0.0)
            self.assertEqual(embedding_b["precision@1"]["numerator"], 0)
            self.assertEqual(embedding_b["precision@1"]["denominator"], 1)
            aggregate = {entry["retrieval configuration"]: entry for entry in data["aggregate metrics"]}
            self.assertEqual(aggregate["embedding-based retrieval"]["precision@1"]["numerator"], 1)
            self.assertEqual(aggregate["embedding-based retrieval"]["precision@1"]["denominator"], 2)
            self.assertEqual(aggregate["embedding-based retrieval"]["precision@1"]["value"], 0.5)
            self.assertEqual(aggregate["embedding-based retrieval"]["recall@1"]["numerator"], 1)
            self.assertEqual(aggregate["embedding-based retrieval"]["recall@1"]["denominator"], 2)
            self.assertEqual(aggregate["lexical retrieval"]["precision@1"]["denominator"], 1)
            self.assertEqual(aggregate["lexical retrieval"]["recall@1"]["denominator"], 2)

    def test_metrics_require_recorded_judgments_and_reject_tampered_c2_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            report, c1 = setup(Path(tmp))
            for case in ("Evaluation Case A", "Evaluation Case B"):
                for configuration in json.loads((CASES / "stage-b-fixture.json").read_text())["retrieval_contract"]["compared retrieval configurations"]:
                    lab04_retrieval.execute_retrieval(report_dir=report, c1_fixture_path=c1, case_id=case,
                        configuration_id=configuration, encoder=Encoder())
            with self.assertRaises(WorkflowError):
                lab04_evaluation.compute_retrieval_metrics(report_dir=report,
                    c3_fixture_path=CASES / "stage-c3-fixture.json", c1_fixture_path=c1, encoder=Encoder())
            tampered = report / "stage-c2" / "evaluation-case-b-lexical-retrieval.json"
            record = json.loads(tampered.read_text())
            record["ranked candidate output"][0]["stable retrieval identifier"] = "F-A"
            tampered.write_text(json.dumps(record))
            judgments = Path(tmp) / "judgments.json"
            judgments.write_text(json.dumps({
                "Evaluation Case A": [{"stable retrieval identifier": "F-A", "relevance judgment": "relevant",
                    "rationale": "F-A states the originating record identifier, record version, and exact sentence span."}],
                "Evaluation Case B": [
                    {"stable retrieval identifier": "F-A", "relevance judgment": "relevant",
                     "rationale": "F-A states the originating record identifier, record version, and exact sentence span."},
                    {"stable retrieval identifier": "F-B", "relevance judgment": "not relevant",
                     "rationale": "F-B records the source and version of the model, not of the supporting passage."}]}))
            lab04_evaluation.record_relevance_judgments(report_dir=report,
                c3_fixture_path=CASES / "stage-c3-fixture.json", judgments_path=judgments, evaluator="student tester")
            with self.assertRaises(WorkflowError):
                lab04_evaluation.compute_retrieval_metrics(report_dir=report,
                    c3_fixture_path=CASES / "stage-c3-fixture.json", c1_fixture_path=c1, encoder=Encoder())


class VerifyAndCliTests(unittest.TestCase):
    def _prepared(self, tmp):
        report, c1 = setup(Path(tmp))
        for case in ("Evaluation Case A", "Evaluation Case B"):
            for configuration in json.loads((CASES / "stage-b-fixture.json").read_text())["retrieval_contract"]["compared retrieval configurations"]:
                lab04_retrieval.execute_retrieval(report_dir=report, c1_fixture_path=c1, case_id=case,
                    configuration_id=configuration, encoder=Encoder())
        judgments = Path(tmp) / "judgments.json"
        judgments.write_text(json.dumps({
            "Evaluation Case A": [{"stable retrieval identifier": "F-A", "relevance judgment": "relevant",
                "rationale": "F-A states the originating record identifier, record version, and exact sentence span, satisfying the relevance judging basis."}],
            "Evaluation Case B": [{"stable retrieval identifier": "F-B", "relevance judgment": "not relevant",
                "rationale": "F-B records the source and version of the model, not of the supporting passage."}]}))
        lab04_evaluation.record_relevance_judgments(report_dir=report,
            c3_fixture_path=CASES / "stage-c3-fixture.json", judgments_path=judgments, evaluator="student tester")
        lab04_evaluation.compute_retrieval_metrics(report_dir=report,
            c3_fixture_path=CASES / "stage-c3-fixture.json", c1_fixture_path=c1, encoder=Encoder())
        return report, c1

    def test_verifier_recomputes_metrics_and_rejects_tampering_and_missing_judgments(self):
        with tempfile.TemporaryDirectory() as tmp:
            report, c1 = self._prepared(tmp)
            verification = lab04_evaluation.verify_stage_c3(report_dir=report,
                c3_fixture_path=CASES / "stage-c3-fixture.json", c1_fixture_path=c1, encoder=Encoder())
            self.assertEqual(verification["outcome"], "passed")
            self.assertEqual(verification["verified metric entries"], 8)
            path = report / "stage-c3" / "retrieval-metrics.json"
            data = json.loads(path.read_text())
            data["per-case metrics"][0]["recall@1"]["value"] = 1.0
            path.write_text(json.dumps(data))
            with self.assertRaises(WorkflowError):
                lab04_evaluation.verify_stage_c3(report_dir=report,
                    c3_fixture_path=CASES / "stage-c3-fixture.json", c1_fixture_path=c1, encoder=Encoder())
            (report / "stage-c3" / "relevance-judgments.json").unlink()
            with self.assertRaises(WorkflowError):
                lab04_evaluation.verify_stage_c3(report_dir=report,
                    c3_fixture_path=CASES / "stage-c3-fixture.json", c1_fixture_path=c1, encoder=Encoder())

    def test_overwrite_refusal_and_symlink_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            report, c1 = self._prepared(tmp)
            with self.assertRaises(WorkflowError):
                lab04_evaluation.compute_retrieval_metrics(report_dir=report,
                    c3_fixture_path=CASES / "stage-c3-fixture.json", c1_fixture_path=c1, encoder=Encoder())
            outside = Path(tmp) / "outside"
            outside.mkdir()
            stage = report / "stage-c3"
            if not any(stage.iterdir()):
                stage.rmdir()
                stage.symlink_to(outside, target_is_directory=True)
                judgments = Path(tmp) / "judgments.json"
                judgments.write_text(json.dumps({
                    "Evaluation Case A": [{"stable retrieval identifier": "F-A", "relevance judgment": "relevant",
                        "rationale": "F-A states the originating record identifier, record version, and exact sentence span."}],
                    "Evaluation Case B": [{"stable retrieval identifier": "F-B", "relevance judgment": "not relevant",
                        "rationale": "F-B records the source and version of the model, not of the supporting passage."}]}))
                with self.assertRaises(WorkflowError):
                    lab04_evaluation.record_relevance_judgments(report_dir=report,
                        c3_fixture_path=CASES / "stage-c3-fixture.json",
                        judgments_path=judgments, evaluator="again")

    def test_malformed_judgments_fixture_and_evaluator_raise_workflow_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            report, c1 = setup(Path(tmp))
            for case in ("Evaluation Case A", "Evaluation Case B"):
                for configuration in json.loads((CASES / "stage-b-fixture.json").read_text())["retrieval_contract"]["compared retrieval configurations"]:
                    lab04_retrieval.execute_retrieval(report_dir=report, c1_fixture_path=c1, case_id=case,
                        configuration_id=configuration, encoder=Encoder())
            broken = Path(tmp) / "broken.json"
            broken.write_text("{not json")
            with self.assertRaises(WorkflowError):
                lab04_evaluation.record_relevance_judgments(report_dir=report,
                    c3_fixture_path=CASES / "stage-c3-fixture.json", judgments_path=broken, evaluator="x")
            wrong = json.loads((CASES / "stage-c3-fixture.json").read_text())
            wrong["expected-result chunking configuration binding"]["chunking configuration"] = "fixed-72-v1"
            bad_fixture = Path(tmp) / "bad-c3.json"
            bad_fixture.write_text(json.dumps(wrong))
            with self.assertRaises(WorkflowError):
                lab04_evaluation.record_relevance_judgments(report_dir=report,
                    c3_fixture_path=bad_fixture, judgments_path=broken, evaluator="x")
            good = Path(tmp) / "good.json"
            good.write_text(json.dumps({
                "Evaluation Case A": [{"stable retrieval identifier": "F-A", "relevance judgment": "relevant",
                    "rationale": "F-A states the originating record identifier, record version, and exact sentence span."}],
                "Evaluation Case B": [{"stable retrieval identifier": "F-B", "relevance judgment": "not relevant",
                    "rationale": "F-B records the source and version of the model, not of the supporting passage."}]}))
            with self.assertRaises(WorkflowError):
                lab04_evaluation.record_relevance_judgments(report_dir=report,
                    c3_fixture_path=CASES / "stage-c3-fixture.json", judgments_path=good, evaluator="")

    def test_cli_records_judgments_computes_metrics_and_verifies(self):
        with tempfile.TemporaryDirectory() as tmp:
            report, c1 = self._prepared(tmp)
            import shutil
            shutil.rmtree(report / "stage-c3")
            judgments = Path(tmp) / "cli-judgments.json"
            judgments.write_text(json.dumps({
                "Evaluation Case A": [{"stable retrieval identifier": "F-A", "relevance judgment": "relevant",
                    "rationale": "F-A states the originating record identifier, record version, and exact sentence span, satisfying the relevance judging basis."}],
                "Evaluation Case B": [{"stable retrieval identifier": "F-B", "relevance judgment": "not relevant",
                    "rationale": "F-B records the source and version of the model, not of the supporting passage."}]}))
            from unittest.mock import patch
            with patch("learning_project.lab04_retrieval.load_local_retrieval_unit_encoder", return_value=Encoder()):
                self.assertEqual(main(["lab04", "record-relevance-judgments", "--report-dir", str(report),
                    "--judgments", str(judgments), "--evaluator", "cli tester"]), 0)
                self.assertEqual(main(["lab04", "compute-retrieval-metrics", "--report-dir", str(report),
                    "--fixture", str(c1)]), 0)
                self.assertEqual(main(["lab04", "verify-stage-c3", "--report-dir", str(report),
                    "--fixture", str(c1)]), 0)
                self.assertEqual(main(["lab04", "measure-operational-evidence", "--report-dir", str(report),
                    "--fixture", str(c1), "--runs", "1"]), 0)
                self.assertEqual(main(["lab04", "record-configuration-decision", "--report-dir", str(report),
                    "--selected-configuration", "embedding-based retrieval", "--decided-by", "cli tester",
                    "--rationale", ("Under the two declared development evaluation cases at configured result count k=1 the recorded "
                                    "relevance judgments give the embedding-based candidate aggregate precision@1 0.5 and recall@1 0.5 "
                                    "while the lexical baseline reports precision@1 0.0 and recall@1 0.0, so the evidence supports "
                                    "adopting the embedding-based retrieval configuration for these declared cases only.")]), 0)


class OperationalEvidenceAndDecisionTests(unittest.TestCase):
    def _prepared(self, tmp):
        report, c1 = setup(Path(tmp))
        for case in ("Evaluation Case A", "Evaluation Case B"):
            for configuration in json.loads((CASES / "stage-b-fixture.json").read_text())["retrieval_contract"]["compared retrieval configurations"]:
                lab04_retrieval.execute_retrieval(report_dir=report, c1_fixture_path=c1, case_id=case,
                    configuration_id=configuration, encoder=Encoder())
        judgments = Path(tmp) / "judgments.json"
        judgments.write_text(json.dumps({
            "Evaluation Case A": [{"stable retrieval identifier": "F-A", "relevance judgment": "relevant",
                "rationale": "F-A states the originating record identifier, record version, and exact sentence span, satisfying the relevance judging basis."}],
            "Evaluation Case B": [{"stable retrieval identifier": "F-B", "relevance judgment": "not relevant",
                "rationale": "F-B records the source and version of the model, not of the supporting passage."}]}))
        lab04_evaluation.record_relevance_judgments(report_dir=report,
            c3_fixture_path=CASES / "stage-c3-fixture.json", judgments_path=judgments, evaluator="student tester")
        lab04_evaluation.compute_retrieval_metrics(report_dir=report,
            c3_fixture_path=CASES / "stage-c3-fixture.json", c1_fixture_path=c1, encoder=Encoder())
        return report, c1

    def test_operational_evidence_measures_each_configuration_with_boundaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            report, c1 = self._prepared(tmp)
            path = lab04_evaluation.measure_operational_evidence(report_dir=report,
                c1_fixture_path=c1, encoder=Encoder(), runs=2)
            data = json.loads(path.read_text())
            self.assertEqual(data["schema_version"], "1.0")
            self.assertEqual([e["retrieval configuration"] for e in data["operational measurements"]],
                             list(json.loads((CASES / "stage-b-fixture.json").read_text())["retrieval_contract"]["compared retrieval configurations"]))
            for entry in data["operational measurements"]:
                for field in ("prepared-index build or update cost", "query latency", "query cost", "resource consumption", "execution failures"):
                    self.assertIn(field, entry, msg=field)
                    measurement = entry[field]
                    self.assertIn("measurement boundary", measurement)
                    self.assertIn("measurement", measurement)
                self.assertEqual(entry["execution failures"]["measurement"], [])
            self.assertIn("operational evidence is not a relevance measure", data["observation boundary"])

    def test_configuration_decision_is_bounded_and_requires_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            report, c1 = self._prepared(tmp)
            rationale = ("Under the two declared development evaluation cases at the configured result count k=1, "
                         "the recorded relevance judgments give the embedding-based candidate retrieval configuration "
                         "aggregate precision@1 0.5 and recall@1 0.5 while the lexical experiment baseline reports "
                         "precision@1 0.0 and recall@1 0.0; the measured query latencies are comparable, so the "
                         "evidence supports adopting the embedding-based retrieval configuration for these declared cases only.")
            path = lab04_evaluation.record_configuration_decision(report_dir=report,
                c3_fixture_path=CASES / "stage-c3-fixture.json", selected_configuration_id="embedding-based retrieval",
                rationale=rationale, decided_by="student tester")
            data = json.loads(path.read_text())
            self.assertEqual(data["selected retrieval configuration"], "embedding-based retrieval")
            self.assertEqual(data["decision boundary"],
                             "bounded to Evaluation Case A and Evaluation Case B, canonical knowledge collection version course-seed-v1, "
                             "the sentence-pair-v1 retrieval-unit boundary, the declared relevance judging basis, and the configured result count k=1")
            self.assertIn("does not authorize any change to the canonical knowledge collection", data["authority boundary"])
            self.assertIn("embedding-based retrieval", data["rationale"])
            with self.assertRaises(WorkflowError):
                lab04_evaluation.record_configuration_decision(report_dir=report,
                    c3_fixture_path=CASES / "stage-c3-fixture.json", selected_configuration_id="hybrid retrieval",
                    rationale="short", decided_by="student tester")

    def test_reads_bom_prefixed_judgments_and_refuses_duplicate_identifiers(self):
        with tempfile.TemporaryDirectory() as tmp:
            report, c1 = setup(Path(tmp))
            for case in ("Evaluation Case A", "Evaluation Case B"):
                for configuration in json.loads((CASES / "stage-b-fixture.json").read_text())["retrieval_contract"]["compared retrieval configurations"]:
                    lab04_retrieval.execute_retrieval(report_dir=report, c1_fixture_path=c1, case_id=case,
                        configuration_id=configuration, encoder=Encoder())
            payload = json.dumps({
                "Evaluation Case A": [{"stable retrieval identifier": "F-A", "relevance judgment": "relevant",
                    "rationale": "F-A states the originating record identifier, record version, and exact sentence span."}],
                "Evaluation Case B": [{"stable retrieval identifier": "F-B", "relevance judgment": "not relevant",
                    "rationale": "F-B records the source and version of the model, not of the supporting passage."}]})
            bom = Path(tmp) / "judgments-bom.json"
            bom.write_bytes(b"\xef\xbb\xbf" + payload.encode("utf-8"))
            path = lab04_evaluation.record_relevance_judgments(report_dir=report,
                c3_fixture_path=CASES / "stage-c3-fixture.json", judgments_path=bom, evaluator="student tester")
            self.assertTrue(path.is_file())
        with tempfile.TemporaryDirectory() as tmp:
            report, c1 = setup(Path(tmp))
            for case in ("Evaluation Case A", "Evaluation Case B"):
                for configuration in json.loads((CASES / "stage-b-fixture.json").read_text())["retrieval_contract"]["compared retrieval configurations"]:
                    lab04_retrieval.execute_retrieval(report_dir=report, c1_fixture_path=c1, case_id=case,
                        configuration_id=configuration, encoder=Encoder())
            duplicated = Path(tmp) / "duplicates.json"
            duplicated.write_text(json.dumps({
                "Evaluation Case A": [
                    {"stable retrieval identifier": "F-A", "relevance judgment": "relevant",
                     "rationale": "F-A states the originating record identifier, record version, and exact sentence span."},
                    {"stable retrieval identifier": "F-A", "relevance judgment": "not relevant",
                     "rationale": "A second judgment for the same returned retrieval unit."}],
                "Evaluation Case B": [{"stable retrieval identifier": "F-B", "relevance judgment": "not relevant",
                    "rationale": "F-B records the source and version of the model, not of the supporting passage."}]}))
            with self.assertRaises(WorkflowError):
                lab04_evaluation.record_relevance_judgments(report_dir=report,
                    c3_fixture_path=CASES / "stage-c3-fixture.json", judgments_path=duplicated, evaluator="student tester")

    def test_extra_judged_identifier_never_returned_stops_the_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            report, c1 = setup(Path(tmp))
            for case in ("Evaluation Case A", "Evaluation Case B"):
                for configuration in json.loads((CASES / "stage-b-fixture.json").read_text())["retrieval_contract"]["compared retrieval configurations"]:
                    lab04_retrieval.execute_retrieval(report_dir=report, c1_fixture_path=c1, case_id=case,
                        configuration_id=configuration, encoder=Encoder())
            extra = Path(tmp) / "extra.json"
            extra.write_text(json.dumps({
                "Evaluation Case A": [
                    {"stable retrieval identifier": "F-A", "relevance judgment": "relevant",
                     "rationale": "F-A states the originating record identifier, record version, and exact sentence span."},
                    {"stable retrieval identifier": "F-Z", "relevance judgment": "not relevant",
                     "rationale": "F-Z was never returned by any compared retrieval configuration."}],
                "Evaluation Case B": [{"stable retrieval identifier": "F-B", "relevance judgment": "not relevant",
                    "rationale": "F-B records the source and version of the model, not of the supporting passage."}]}))
            with self.assertRaises(WorkflowError):
                lab04_evaluation.record_relevance_judgments(report_dir=report,
                    c3_fixture_path=CASES / "stage-c3-fixture.json", judgments_path=extra, evaluator="student tester")

    def test_aggregate_precision_is_undefined_when_no_returned_unit_was_judged(self):
        entries = []
        for case in ("Evaluation Case A", "Evaluation Case B"):
            entries.append({
                "retrieval configuration": "lexical retrieval",
                "evaluation case": case,
                "ranked candidate output": [],
                "judged returned retrieval units": [],
                "precision@1": {"numerator": 0, "denominator": 0, "value": "undefined",
                                "reason": "undefined because no returned retrieval unit was available for a relevance judgment"},
                "recall@1": {"numerator": 0, "denominator": 1, "value": 0.0},
            })
        aggregate = lab04_evaluation._aggregate(entries, "lexical retrieval", 1)
        self.assertEqual(aggregate["precision@1"]["value"], "undefined")
        self.assertEqual(aggregate["precision@1"]["denominator"], 0)
        self.assertEqual(aggregate["recall@1"]["denominator"], 2)
        self.assertEqual(aggregate["recall@1"]["value"], 0.0)
