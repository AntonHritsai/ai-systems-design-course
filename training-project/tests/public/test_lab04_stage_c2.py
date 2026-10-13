"""Stage C2 retrieval contract tests using actual Stage B/C1 evidence."""
import json
import math
import os
import tempfile
import unittest
from pathlib import Path

from learning_project import lab04_index, lab04_retrieval
from learning_project.cli import main
from learning_project.lab04 import prepare_boundary_comparison, record_boundary_decision
from learning_project.workflow import WorkflowError

CASES = Path(__file__).resolve().parents[2] / "cases" / "lab04"


class Encoder:
    embedding_model = "test-model"
    model_revision = "v1"
    representation_version = "test-v1"
    embedding_dimension = 3
    embedding_space = "test-model/v1"

    def encode(self, texts):
        return [[1.0, 0.0, 0.0] if "auditor" in text or "provenance link" in text else [0.5, 0.5, 0.0] for text in texts]


def setup(directory):
    report = directory / "report"
    prepare_boundary_comparison(fixture_path=CASES / "stage-b-fixture.json", report_dir=report)
    record_boundary_decision(report_dir=report, selected_chunking_configuration_id="sentence-pair-v1", rationale="Preserves context", student="tester")
    fixture = json.loads((CASES / "stage-c1-fixture.json").read_text())
    e = Encoder()
    fixture["representation_contract"] = {
        "embedding model": e.embedding_model, "model revision": e.model_revision,
        "representation version": e.representation_version, "embedding dimension": e.embedding_dimension,
        "embedding space": e.embedding_space,
        "vector-similarity measure": "cosine similarity with the untransformed [-1, 1] score convention",
        "input normalization": "Unicode NFC followed by stripping leading and trailing whitespace; an empty normalized input is refused",
    }
    c1 = directory / "c1.json"
    c1.write_text(json.dumps(fixture))
    lab04_index.prepare_retrieval_unit_embeddings(report_dir=report, fixture_path=c1, encoder=e)
    lab04_index.prepare_vector_index(report_dir=report, fixture_path=c1)
    lab04_index.check_index_bindings(report_dir=report, fixture_path=c1, required_retrieval_configuration_id="required-course-seed-v1")
    lab04_index.check_index_bindings(report_dir=report, fixture_path=c1, required_retrieval_configuration_id="required-course-seed-v2")
    return report, c1


class RetrievalTests(unittest.TestCase):
    def test_missing_stage_b_evidence_raises_workflow_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(WorkflowError, "Cannot read Stage B evidence"):
                lab04_retrieval.execute_retrieval(
                    report_dir=Path(tmp) / "report",
                    case_id="Evaluation Case A",
                    configuration_id="lexical retrieval",
                )

    def test_lexical_case_a_empty_and_case_b_ranked_with_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            report, c1 = setup(Path(tmp))
            for case, expected in [("Evaluation Case A", []), ("Evaluation Case B", ["F-B"])]:
                path = lab04_retrieval.execute_retrieval(report_dir=report, c1_fixture_path=c1, case_id=case,
                    configuration_id="lexical retrieval", encoder=Encoder())
                result = json.loads(path.read_text())
                self.assertEqual([v["stable retrieval identifier"] for v in result["ranked candidate output"]], expected)
                self.assertEqual(result["canonical knowledge collection version"], "course-seed-v1")
                self.assertEqual(result["text query"], json.loads((CASES / "stage-b-fixture.json").read_text())["evaluation_cases"][0 if case.endswith("A") else 1]["operation_input"]["text query"])
                self.assertNotIn("evaluator", json.dumps(result).lower())
                for candidate in result["ranked candidate output"]:
                    self.assertIn("character_span", candidate["provenance link"])

    def test_embedding_uses_exact_cosine_and_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            report, c1 = setup(Path(tmp))
            path = lab04_retrieval.execute_retrieval(report_dir=report, c1_fixture_path=c1,
                case_id="Evaluation Case A", configuration_id="embedding-based retrieval", encoder=Encoder())
            result = json.loads(path.read_text())
            self.assertEqual(len(result["ranking evidence"]["embedding ranking"]), 2)
            self.assertEqual(result["ranking evidence"]["embedding ranking"][0]["stable retrieval identifier"], "F-A")
            self.assertEqual(len(result["ranked candidate output"]), 1)
            self.assertEqual(result["ranked candidate output"][0]["stable retrieval identifier"], "F-A")
            self.assertNotIn("evaluator", json.dumps(result).lower())
            with self.assertRaises(WorkflowError):
                lab04_retrieval.execute_retrieval(report_dir=report, c1_fixture_path=c1,
                    case_id="Evaluation Case A", configuration_id="embedding-based retrieval",
                    encoder=Encoder(), required_retrieval_configuration_id="required-course-seed-v2")

    def test_hybrid_normalizes_independent_rankings(self):
        with tempfile.TemporaryDirectory() as tmp:
            report, c1 = setup(Path(tmp))
            path = lab04_retrieval.execute_retrieval(report_dir=report, c1_fixture_path=c1,
                case_id="Evaluation Case B", configuration_id="hybrid retrieval", encoder=Encoder())
            result = json.loads(path.read_text())
            evidence = result["ranking evidence"]
            self.assertEqual(len(evidence["lexical ranking"]), 2)
            self.assertEqual(len(evidence["embedding ranking"]), 2)
            self.assertEqual(set(x["stable retrieval identifier"] for x in evidence["hybrid ranking"]), {"F-A", "F-B"})
            for x in evidence["hybrid ranking"]:
                identifier = x["stable retrieval identifier"]
                lex = next((v["score"] for v in evidence["lexical ranking"] if v["stable retrieval identifier"] == identifier), 0)
                emb = next((v["score"] for v in evidence["embedding ranking"] if v["stable retrieval identifier"] == identifier), 0)
                expected = lex / max(v["score"] for v in evidence["lexical ranking"]) + emb / max(v["score"] for v in evidence["embedding ranking"])
                self.assertAlmostEqual(x["score"], expected)
            self.assertEqual(result["ranked candidate output"][0]["stable retrieval identifier"], evidence["hybrid ranking"][0]["stable retrieval identifier"])

    def test_reranking_only_scores_lexical_candidate_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            report, c1 = setup(Path(tmp))
            for case in ("Evaluation Case A", "Evaluation Case B"):
                path = lab04_retrieval.execute_retrieval(report_dir=report, c1_fixture_path=c1,
                    case_id=case, configuration_id="lexical retrieval followed by embedding-based reranking", encoder=Encoder())
                result = json.loads(path.read_text())
                bounded = result["ranking evidence"]["bounded candidate set"]
                self.assertEqual(bounded, result["ranking evidence"]["lexical ranking"][:2])
                ranked = result["ranking evidence"]["reranked candidate set"]
                self.assertEqual(set(x["stable retrieval identifier"] for x in ranked), set(x["stable retrieval identifier"] for x in bounded))
                self.assertEqual(len(result["ranked candidate output"]), min(1, len(bounded)))

    def test_verifier_recomputes_all_eight_outputs_and_rejects_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            report, c1 = setup(Path(tmp))
            for case in ("Evaluation Case A", "Evaluation Case B"):
                for configuration in json.loads((CASES / "stage-b-fixture.json").read_text())["retrieval_contract"]["compared retrieval configurations"]:
                    lab04_retrieval.execute_retrieval(report_dir=report, c1_fixture_path=c1,
                        case_id=case, configuration_id=configuration, encoder=Encoder())
            self.assertEqual(lab04_retrieval.verify_stage_c2(report_dir=report, c1_fixture_path=c1, encoder=Encoder())["outcome"], "passed")
            path = report / "stage-c2" / "evaluation-case-b-hybrid-retrieval.json"
            result = json.loads(path.read_text())
            result["ranking evidence"]["hybrid ranking"][0]["score"] = -20
            path.write_text(json.dumps(result))
            with self.assertRaises(WorkflowError):
                lab04_retrieval.verify_stage_c2(report_dir=report, c1_fixture_path=c1, encoder=Encoder())

    def test_verifier_rejects_stale_required_pre_use_binding_despite_matching_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            report, c1 = setup(Path(tmp))
            for case in ("Evaluation Case A", "Evaluation Case B"):
                for configuration in json.loads((CASES / "stage-b-fixture.json").read_text())["retrieval_contract"]["compared retrieval configurations"]:
                    lab04_retrieval.execute_retrieval(report_dir=report, c1_fixture_path=c1,
                        case_id=case, configuration_id=configuration, encoder=Encoder())
            fixture = json.loads(c1.read_text())
            required = lab04_index._required_configuration(fixture, "required-course-seed-v1")
            required["the canonical knowledge collection version"] = "course-seed-v2"
            c1.write_text(json.dumps(fixture))
            manifest = json.loads((report / "stage-c1" / "index-manifest.json").read_text())
            checks, failed = lab04_index._compare_bindings(fixture, manifest, required, report)
            self.assertIsNotNone(failed)
            record_path = report / "stage-c1" / "binding-check-required-course-seed-v1.json"
            record = json.loads(record_path.read_text())
            record.update({"checked bindings": checks, "outcome": "stale", "failed binding": failed})
            record_path.write_text(json.dumps(record))
            self.assertEqual(lab04_index.verify_stage_c1(report_dir=report, fixture_path=c1)["outcome"], "passed")
            with self.assertRaises(WorkflowError):
                lab04_retrieval.verify_stage_c2(report_dir=report, c1_fixture_path=c1, encoder=Encoder())

    def test_cli_executes_and_verifies(self):
        with tempfile.TemporaryDirectory() as tmp:
            report, c1 = setup(Path(tmp))
            from unittest.mock import patch
            with patch("learning_project.lab04_retrieval.load_local_retrieval_unit_encoder", return_value=Encoder()):
                for case in ("Evaluation Case A", "Evaluation Case B"):
                    for configuration in json.loads((CASES / "stage-b-fixture.json").read_text())["retrieval_contract"]["compared retrieval configurations"]:
                        self.assertEqual(main(["lab04", "execute-retrieval", "--report-dir", str(report),
                            "--fixture", str(c1), "--case-id", case, "--configuration-id", configuration]), 0)
                self.assertEqual(main(["lab04", "verify-stage-c2", "--report-dir", str(report), "--fixture", str(c1)]), 0)

    def test_fixture_declares_bounded_configurations_and_content_word_rule(self):
        fixture = json.loads((CASES / "stage-c2-fixture.json").read_text())
        self.assertEqual(fixture["schema_version"], "1.0")
        self.assertEqual(fixture["result count k"], 1)
        self.assertEqual(fixture["reranking candidate count"], 2)
        self.assertEqual(fixture["lexical rule"], "lowercase exact alphabetic content-word overlap; distinct shared tokens counted once")
        self.assertEqual(fixture["hybrid rule"], "divide each independent ranking score by its ranking maximum, add by stable retrieval identifier; empty ranking contributes nothing")
        self.assertEqual(fixture["tie order"], "stable retrieval identifier ascending")

    def test_rejects_invalid_query_embeddings_and_output_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            report, c1 = setup(Path(tmp))
            for vector in ([0.0, 0.0, 0.0], [float("nan"), 0.0, 1.0], [1.0, 0.0]):
                class Broken(Encoder):
                    def encode(self, texts):
                        return [vector] if len(texts) == 1 and "auditor" in texts[0] else super().encode(texts)
                with self.assertRaises(WorkflowError):
                    lab04_retrieval.execute_retrieval(report_dir=report, c1_fixture_path=c1,
                        case_id="Evaluation Case A", configuration_id="embedding-based retrieval", encoder=Broken())
            path = lab04_retrieval.execute_retrieval(report_dir=report, c1_fixture_path=c1,
                case_id="Evaluation Case A", configuration_id="lexical retrieval")
            with self.assertRaises(WorkflowError):
                lab04_retrieval.execute_retrieval(report_dir=report, c1_fixture_path=c1,
                    case_id="Evaluation Case A", configuration_id="lexical retrieval")
            path.unlink()
            path.symlink_to(Path(tmp) / "outside")
            with self.assertRaises(WorkflowError):
                lab04_retrieval.execute_retrieval(report_dir=report, c1_fixture_path=c1,
                    case_id="Evaluation Case A", configuration_id="lexical retrieval")

    def test_rejects_symlinked_stage_c2_directory_without_writing_outside_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            report, c1 = setup(Path(tmp))
            outside = Path(tmp) / "outside"
            outside.mkdir()
            (report / "stage-c2").symlink_to(outside, target_is_directory=True)
            destination = outside / "evaluation-case-a-lexical-retrieval.json"
            with self.assertRaises(WorkflowError):
                lab04_retrieval.execute_retrieval(report_dir=report, c1_fixture_path=c1,
                    case_id="Evaluation Case A", configuration_id="lexical retrieval")
            self.assertFalse(destination.exists())

    @unittest.skipUnless(os.name == "posix" and hasattr(os, "O_NOFOLLOW"), "POSIX no-follow required")
    def test_directory_swap_at_final_open_does_not_write_outside(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            report, c1 = setup(Path(tmp))
            stage = report / "stage-c2"
            outside = Path(tmp) / "outside"
            outside.mkdir()
            destination = outside / "evaluation-case-a-lexical-retrieval.json"
            original_open = os.open
            swapped = False

            def swap_before_open(path, *args, **kwargs):
                nonlocal swapped
                if not swapped and Path(path) in (stage, Path("stage-c2"), stage / destination.name):
                    swapped = True
                    if stage.exists():
                        stage.rmdir()
                    stage.symlink_to(outside, target_is_directory=True)
                return original_open(path, *args, **kwargs)

            with patch("os.open", side_effect=swap_before_open):
                with self.assertRaises(WorkflowError):
                    lab04_retrieval.execute_retrieval(report_dir=report, c1_fixture_path=c1,
                        case_id="Evaluation Case A", configuration_id="lexical retrieval")
            self.assertTrue(swapped)
            self.assertFalse(destination.exists())

    def test_rejects_contradictory_embedding_rule(self):
        with tempfile.TemporaryDirectory() as tmp:
            wrong = json.loads((CASES / "stage-c2-fixture.json").read_text())
            wrong["embedding rule"] = "skip the Stage C1 contract and use arbitrary scores"
            path = Path(tmp) / "invalid-c2.json"
            path.write_text(json.dumps(wrong))
            with self.assertRaises(WorkflowError):
                lab04_retrieval._c2_configuration(path)

    def test_rejects_contradictory_reranking_rule(self):
        with tempfile.TemporaryDirectory() as tmp:
            wrong = json.loads((CASES / "stage-c2-fixture.json").read_text())
            wrong["reranking rule"] = "rerank every indexed unit instead of the bounded lexical set"
            path = Path(tmp) / "invalid-c2.json"
            path.write_text(json.dumps(wrong))
            with self.assertRaises(WorkflowError):
                lab04_retrieval._c2_configuration(path)

    def test_null_excluded_words_raise_workflow_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            wrong = json.loads((CASES / "stage-c2-fixture.json").read_text())
            wrong["excluded lexical function words"] = None
            path = Path(tmp) / "invalid-c2.json"
            path.write_text(json.dumps(wrong))
            with self.assertRaises(WorkflowError):
                lab04_retrieval._c2_configuration(path)

    def test_rejects_invalid_stage_c2_configuration_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            report, c1 = setup(Path(tmp))
            wrong = json.loads((CASES / "stage-c2-fixture.json").read_text())
            wrong["result count k"] = 3
            path = Path(tmp) / "invalid-c2.json"
            path.write_text(json.dumps(wrong))
            with self.assertRaises(WorkflowError):
                lab04_retrieval.execute_retrieval(report_dir=report, c1_fixture_path=c1,
                    c2_fixture_path=path, case_id="Evaluation Case A", configuration_id="lexical retrieval")

    def test_rejects_malformed_upstream_evidence_with_workflow_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            report, c1 = setup(Path(tmp))
            manifest_file = report / "stage-c1" / "index-manifest.json"
            manifest = json.loads(manifest_file.read_text())
            manifest["a stable retrieval identifier and provenance link for every retrieval unit"] = [None]
            manifest_file.write_text(json.dumps(manifest))
            with self.assertRaises(WorkflowError):
                lab04_retrieval.execute_retrieval(report_dir=report, c1_fixture_path=c1,
                    case_id="Evaluation Case A", configuration_id="lexical retrieval")

    def test_rejects_tampered_stage_b_and_c1_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            report, c1 = setup(Path(tmp))
            vector_file = report / "stage-c1" / "retrieval-unit-embeddings.json"
            artifact = json.loads(vector_file.read_text())
            artifact["retrieval-unit embeddings"][0]["retrieval-unit embedding"] = [0.0, 1.0, 0.0]
            vector_file.write_text(json.dumps(artifact))
            with self.assertRaises(WorkflowError):
                lab04_retrieval.execute_retrieval(report_dir=report, c1_fixture_path=c1,
                    case_id="Evaluation Case A", configuration_id="embedding-based retrieval", encoder=Encoder())
            vector_file.write_text(json.dumps({**artifact, "retrieval-unit embeddings": []}))
            with self.assertRaises(WorkflowError):
                lab04_retrieval.execute_retrieval(report_dir=report, c1_fixture_path=c1,
                    case_id="Evaluation Case A", configuration_id="lexical retrieval", encoder=Encoder())
