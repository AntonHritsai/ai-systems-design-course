"""Public tests for the Laboratory 04 Stage C1 embeddings-and-index slice."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from learning_project import lab04_index
from learning_project.cli import main
from learning_project.lab04 import prepare_boundary_comparison, record_boundary_decision
from learning_project.workflow import WorkflowError


CASES = Path(__file__).resolve().parents[2] / "cases" / "lab04"
STAGE_B_FIXTURE = CASES / "stage-b-fixture.json"
STAGE_C1_FIXTURE = CASES / "stage-c1-fixture.json"
REAL_MODEL_DIR = os.environ.get("LAB04_REAL_MODEL_DIR")


class _StubEncoder:
    """Deterministic stand-in for the declared local embedding model."""

    def __init__(self, **overrides: object) -> None:
        self.embedding_model = "course-test-model"
        self.model_revision = "revision-1"
        self.representation_version = "course-static-embed-v1"
        self.embedding_dimension = 256
        self.embedding_space = "course-test-model@revision-1/course-static-embed-v1"
        for key, value in overrides.items():
            setattr(self, key, value)

    def encode(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def _vector(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values: list[float] = []
        counter = 0
        while len(values) < int(self.embedding_dimension):
            block = hashlib.sha256(digest + counter.to_bytes(2, "big")).digest()
            values.extend(round((byte / 255.0) * 2.0 - 1.0, 6) for byte in block)
            counter += 1
        return values[: int(self.embedding_dimension)]


class _LyingEncoder(_StubEncoder):
    """Declares the contract while returning vectors of another length."""

    def _vector(self, text: str) -> list[float]:
        return [0.5] * 8


def _write_stage_c1_fixture(directory: Path, encoder: _StubEncoder) -> Path:
    fixture = json.loads(STAGE_C1_FIXTURE.read_text(encoding="utf-8"))
    fixture["representation_contract"] = {
        "embedding model": encoder.embedding_model,
        "model revision": encoder.model_revision,
        "representation version": encoder.representation_version,
        "embedding dimension": encoder.embedding_dimension,
        "embedding space": encoder.embedding_space,
        "vector-similarity measure": "cosine similarity with the untransformed [-1, 1] score convention",
        "input normalization": "Unicode NFC followed by stripping leading and trailing whitespace; an empty normalized input is refused",
    }
    path = directory / "stage-c1-fixture.json"
    path.write_text(json.dumps(fixture, indent=2) + "\n", encoding="utf-8")
    return path


def _stage_b_report(directory: Path) -> Path:
    report_dir = directory / "reports" / "lab04"
    prepare_boundary_comparison(fixture_path=STAGE_B_FIXTURE, report_dir=report_dir)
    record_boundary_decision(
        report_dir=report_dir,
        selected_chunking_configuration_id="sentence-pair-v1",
        rationale="The sentence-pair boundary rule preserves the originating-record relationship.",
        student="student-01",
        fixture_path=STAGE_B_FIXTURE,
    )
    return report_dir


def _prepare_embeddings(directory: Path, encoder: _StubEncoder) -> tuple[Path, Path]:
    report_dir = _stage_b_report(directory)
    fixture_path = _write_stage_c1_fixture(directory, encoder)
    lab04_index.prepare_retrieval_unit_embeddings(
        report_dir=report_dir,
        fixture_path=fixture_path,
        encoder=encoder,
    )
    return report_dir, fixture_path


class Lab04StageC1EmbeddingTests(unittest.TestCase):
    def test_prepare_retrieval_unit_embeddings_is_compatible_deterministic_and_complete(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            report_dir, _ = _prepare_embeddings(directory, _StubEncoder())
            artifact = json.loads(
                (report_dir / "stage-c1" / "retrieval-unit-embeddings.json").read_text(encoding="utf-8")
            )
            self.assertEqual(artifact["chunking configuration"], "sentence-pair-v1")
            self.assertEqual(
                [unit["stable retrieval identifier"] for unit in artifact["retrieval-unit embeddings"]],
                ["F-A", "F-B"],
            )
            for unit in artifact["retrieval-unit embeddings"]:
                self.assertEqual(len(unit["retrieval-unit embedding"]), 256)
                self.assertEqual(unit["embedding dimension"], 256)
                self.assertEqual(unit["embedding space"], _StubEncoder().embedding_space)
                self.assertIn("character_span", unit["provenance link"])
            first = (report_dir / "stage-c1" / "retrieval-unit-embeddings.json").read_bytes()

            second_report, _ = _prepare_embeddings(directory / "second", _StubEncoder())
            second = (second_report / "stage-c1" / "retrieval-unit-embeddings.json").read_bytes()
            self.assertEqual(first, second)

    def test_prepare_retrieval_unit_embeddings_refuses_an_encoder_outside_the_declared_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report_dir = _stage_b_report(Path(temp))
            fixture_path = _write_stage_c1_fixture(Path(temp), _StubEncoder())
            with self.assertRaisesRegex(WorkflowError, "representation contract"):
                lab04_index.prepare_retrieval_unit_embeddings(
                    report_dir=report_dir,
                    fixture_path=fixture_path,
                    encoder=_StubEncoder(embedding_space="other-model@revision-9/other-space"),
                )

    def test_prepare_retrieval_unit_embeddings_refuses_a_vector_of_another_length(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report_dir = _stage_b_report(Path(temp))
            fixture_path = _write_stage_c1_fixture(Path(temp), _StubEncoder())
            with self.assertRaisesRegex(WorkflowError, "embedding dimension"):
                lab04_index.prepare_retrieval_unit_embeddings(
                    report_dir=report_dir,
                    fixture_path=fixture_path,
                    encoder=_LyingEncoder(),
                )

    def test_prepare_retrieval_unit_embeddings_stops_when_the_local_model_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report_dir = _stage_b_report(Path(temp))
            with self.assertRaisesRegex(WorkflowError, "fetch-embedding-model"):
                lab04_index.prepare_retrieval_unit_embeddings(
                    report_dir=report_dir,
                    fixture_path=STAGE_C1_FIXTURE,
                    model_dir=Path(temp) / "absent-model",
                )

    def test_course_representation_contract_declares_the_pinned_local_embedding_model(self) -> None:
        fixture = json.loads(STAGE_C1_FIXTURE.read_text(encoding="utf-8"))
        contract = fixture["representation_contract"]
        self.assertEqual(contract["embedding model"], "minishlab/potion-base-8M")
        self.assertEqual(contract["model revision"], "bf8b056651a2c21b8d2565580b8569da283cab23")
        self.assertEqual(contract["embedding dimension"], 256)
        self.assertIn("potion-base-8M@", contract["embedding space"])
        self.assertEqual(len(fixture["declared_bindings"]), 5)


class Lab04StageC1IndexTests(unittest.TestCase):
    def test_prepare_vector_index_records_every_declared_binding_and_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report_dir, fixture_path = _prepare_embeddings(Path(temp), _StubEncoder())
            manifest_path = lab04_index.prepare_vector_index(report_dir=report_dir, fixture_path=fixture_path)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for binding in json.loads(fixture_path.read_text(encoding="utf-8"))["declared_bindings"]:
                self.assertIn(binding, manifest)
            self.assertEqual(manifest["index version"], "vector-index-course-seed-v1")
            self.assertEqual(len(manifest["a stable retrieval identifier and provenance link for every retrieval unit"]), 2)
            self.assertIn("complete for the declared chunking configuration", manifest["completeness status"])

            with self.assertRaisesRegex(WorkflowError, "already exists"):
                lab04_index.prepare_vector_index(report_dir=report_dir, fixture_path=fixture_path)

    def test_check_index_bindings_distinguishes_admissible_from_the_rebuild_condition(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report_dir, fixture_path = _prepare_embeddings(Path(temp), _StubEncoder())
            lab04_index.prepare_vector_index(report_dir=report_dir, fixture_path=fixture_path)

            admissible = lab04_index.check_index_bindings(
                report_dir=report_dir,
                fixture_path=fixture_path,
                required_retrieval_configuration_id="required-course-seed-v1",
            )
            self.assertEqual(admissible["outcome"], "admissible")
            self.assertIsNone(admissible["failed binding"])

            stale = lab04_index.check_index_bindings(
                report_dir=report_dir,
                fixture_path=fixture_path,
                required_retrieval_configuration_id="required-course-seed-v2",
            )
            self.assertEqual(stale["outcome"], "stale")
            self.assertEqual(stale["failed binding"], "the canonical knowledge collection version")
            self.assertIn("replacement index version", stale["rebuild condition"])

            with self.assertRaisesRegex(WorkflowError, "Unknown required retrieval configuration"):
                lab04_index.check_index_bindings(
                    report_dir=report_dir,
                    fixture_path=fixture_path,
                    required_retrieval_configuration_id="required-course-seed-v9",
                )

    def test_verify_stage_c1_rejects_a_tampered_retrieval_unit_embedding_dimension(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report_dir, fixture_path = _prepare_embeddings(Path(temp), _StubEncoder())
            lab04_index.prepare_vector_index(report_dir=report_dir, fixture_path=fixture_path)
            for required in ("required-course-seed-v1", "required-course-seed-v2"):
                lab04_index.check_index_bindings(
                    report_dir=report_dir,
                    fixture_path=fixture_path,
                    required_retrieval_configuration_id=required,
                )
            self.assertEqual(
                lab04_index.verify_stage_c1(report_dir=report_dir, fixture_path=fixture_path)["outcome"],
                "passed",
            )

            embeddings_path = report_dir / "stage-c1" / "retrieval-unit-embeddings.json"
            artifact = json.loads(embeddings_path.read_text(encoding="utf-8"))
            artifact["retrieval-unit embeddings"][0]["retrieval-unit embedding"] = [0.1, 0.2]
            embeddings_path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")

            with self.assertRaisesRegex(WorkflowError, "embedding dimension"):
                lab04_index.verify_stage_c1(report_dir=report_dir, fixture_path=fixture_path)


class Lab04StageC1CommandLineTests(unittest.TestCase):
    def test_cli_prepares_the_index_and_reports_both_binding_checks(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            report_dir, fixture_path = _prepare_embeddings(directory, _StubEncoder())

            self.assertEqual(
                main(["lab04", "prepare-index", "--report-dir", str(report_dir), "--fixture", str(fixture_path)]),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "lab04",
                        "check-index-bindings",
                        "--report-dir",
                        str(report_dir),
                        "--fixture",
                        str(fixture_path),
                        "--required-retrieval-configuration-id",
                        "required-course-seed-v1",
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "lab04",
                        "check-index-bindings",
                        "--report-dir",
                        str(report_dir),
                        "--fixture",
                        str(fixture_path),
                        "--required-retrieval-configuration-id",
                        "required-course-seed-v2",
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(["lab04", "verify-stage-c1", "--report-dir", str(report_dir), "--fixture", str(fixture_path)]),
                0,
            )

    def test_cli_stops_when_the_mandatory_local_model_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            report_dir = _stage_b_report(directory)
            code = main(
                [
                    "lab04",
                    "prepare-embeddings",
                    "--report-dir",
                    str(report_dir),
                    "--model-dir",
                    str(directory / "absent-model"),
                ]
            )
            self.assertEqual(code, 1)


@unittest.skipUnless(REAL_MODEL_DIR, "LAB04_REAL_MODEL_DIR is not set")
class Lab04StageC1LocalModelTests(unittest.TestCase):
    def test_declared_local_model_reproduces_the_declared_dimension_deterministically(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report_dir = _stage_b_report(Path(temp))
            lab04_index.prepare_retrieval_unit_embeddings(
                report_dir=report_dir,
                fixture_path=STAGE_C1_FIXTURE,
                model_dir=Path(REAL_MODEL_DIR),
            )
            artifact = json.loads(
                (report_dir / "stage-c1" / "retrieval-unit-embeddings.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                [len(unit["retrieval-unit embedding"]) for unit in artifact["retrieval-unit embeddings"]],
                [256, 256],
            )


if __name__ == "__main__":
    unittest.main()
