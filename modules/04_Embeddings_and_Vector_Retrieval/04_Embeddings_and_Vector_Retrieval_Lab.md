# Module 04: Embeddings and Vector Retrieval — Laboratory

> **Status:** Ready for Students — English laboratory and Ukrainian translation approved by the instructor on 2026-10-13

## Goal

Obtain the evidence that the engineering team needs to decide whether the candidate retrieval configuration — `embedding-based retrieval` — should replace the experiment-baseline retrieval configuration — `lexical retrieval` — for the evaluated use of the retrieval operation over the canonical knowledge collection `course-seed-v1`.

## Tasks

- Apply two supplied chunking configurations to the canonical knowledge records of `course-seed-v1` and select the boundary rule that preserves the meaning required by the declared evaluation cases.
- Produce compatible retrieval-unit embeddings under `representation_contract` in `cases/lab04/stage-c1-fixture.json`, prepare a versioned vector index, and observe a pre-use binding check classifying the vector index as stale for an incompatible required retrieval configuration.
- Execute the declared text queries under four compared retrieval configurations and inspect the ranked candidate output of each execution.
- Record one relevance judgment per returned retrieval unit and evaluation case, compute `precision@1` and `recall@1` from explicit numerators and denominators, and measure the operational evidence.
- State one bounded configuration decision for the declared evaluation cases.

## Expected result

After completing the laboratory, the student holds the evidence that the bounded configuration decision rests on:

- `stage-b/boundary-comparison.json` — both supplied chunking configurations applied to the canonical knowledge records, with the source fragments each configuration selects;
- `stage-b/boundary-decision.yaml` — the recorded choice of the boundary rule that preserves the meaning the declared evaluation cases require;
- `stage-c1/retrieval-unit-embeddings.json` — one compatible retrieval-unit embedding per retrieval unit of the selected chunking configuration;
- `stage-c1/index-manifest.json` — the versioned record of the vector index: its canonical knowledge collection version, its representation bindings, its chunking binding, and the stable retrieval identifier and provenance link of every indexed retrieval unit;
- two pre-use binding check records — the vector index classified as admissible for a compatible required retrieval configuration and as stale for an incompatible one;
- eight ranked candidate output files in `stage-c2/` — the ranked retrieval units that each of the four compared retrieval configurations returned for each of the two declared evaluation cases;
- `stage-c3/relevance-judgments.json` — one relevance judgment with its rationale for every returned retrieval unit and evaluation case;
- `stage-c3/retrieval-metrics.json` — `precision@1` and `recall@1` for every retrieval configuration and evaluation case, computed from explicit numerators and denominators;
- `stage-c3/operational-evidence.json` — the measured query latency of each retrieval configuration, kept outside every metric numerator and denominator;
- `stage-c3/configuration-decision.json` — one bounded configuration decision with its decision boundary and its authority boundary;
- the `reports/lab04/` report directory passing `verify-stage-c3`.

## Expected competencies

After completing the laboratory, the student can:

- Apply a chunking configuration to canonical knowledge records and select the boundary rule that preserves the meaning required by declared evaluation cases.
- Produce compatible retrieval-unit embeddings under the representation contract declared in `cases/lab04/stage-c1-fixture.json`, prepare a versioned vector index, and verify the index manifest's collection-version binding independently against `required-course-seed-v1` and `required-course-seed-v2` in that fixture, its representation bindings against `representation_contract` in that fixture, its chunking binding against `reports/lab04/stage-b/boundary-decision.yaml`, and its per-unit stable-retrieval-identifier and provenance-link bindings against the selected source fragments in `reports/lab04/stage-b/boundary-comparison.json`.
- Execute four retrieval configurations over declared text queries and distinguish the ranked candidate output from relevance, from the contents of the canonical knowledge collection, and from the downstream model-backed operation.
- Apply the declared relevance judging basis to every returned retrieval unit, record one judgment per returned retrieval unit and evaluation case, and state the rationale for each judgment.
- Compute `precision@1` and `recall@1` with explicit numerators and denominators, including the undefined treatment of `precision@1` for an empty ranked candidate output.
- State one bounded configuration decision with its decision boundary and authority boundary, and confirm that the decision neither establishes downstream concept-definition quality nor authorizes a change to the canonical knowledge collection.

## Prerequisites

- Laboratories 01–03 completed.
- `uv sync --extra lab04` executed from `AI_Systems_Design/training-project`.
- The declared local embedding model acquired with `fetch-embedding-model` (Student Step 4).

## Starting state

Run all commands from `AI_Systems_Design/training-project`.

The course supplies:

- canonical knowledge records `R-A` and `R-B` as `course-seed-v1`;
- two chunking configurations, `sentence-pair-v1` and `fixed-72-v1`;
- two evaluation cases, `Evaluation Case A` and `Evaluation Case B`, with their text queries and evaluator-only expected results;
- four compared retrieval configurations;
- the local embedding model `minishlab/potion-base-8M` at revision `bf8b056651a2c21b8d2565580b8569da283cab23`.

The Stage C1 authority is `cases/lab04/stage-c1-fixture.json`. Its `representation_contract` declares:

- embedding model `minishlab/potion-base-8M`;
- model revision `bf8b056651a2c21b8d2565580b8569da283cab23`;
- representation version `course-static-embed-v1`;
- embedding dimension `256`;
- embedding space `potion-base-8M@bf8b056651a2c21b8d2565580b8569da283cab23/course-static-embed-v1`.

Its `required_retrieval_configurations` entries supply the required canonical knowledge collection version. For a binding check:

- the required chunking value comes from `reports/lab04/stage-b/boundary-decision.yaml`;
- the required per-unit stable retrieval identifiers and provenance links come from the selected source fragments in `reports/lab04/stage-b/boundary-comparison.json`.

The student performs:

- execution of every declared laboratory operation;
- inspection of every returned retrieval unit and provenance link;
- recording of relevance judgments under the declared relevance judging basis;
- verification of every explicit numerator and denominator;
- the bounded configuration decision.

## Steps

### Student Step 1 — Apply both supplied chunking configurations

```bash
uv run learning-project lab04 prepare-boundaries --report-dir reports/lab04
```

Windows PowerShell:

```powershell
uv run learning-project lab04 prepare-boundaries --report-dir reports/lab04
```

The command applies `sentence-pair-v1` and `fixed-72-v1` to canonical knowledge records `R-A` and `R-B` and writes `reports/lab04/stage-b/boundary-comparison.json`. The `sentence-pair-v1` boundary rule uses a chunk size of at most two sentences with no overlap. The `fixed-72-v1` boundary rule uses a chunk size of at most 72 characters with no overlap. Every source fragment records a stable retrieval identifier, the text of the source fragment, canonical knowledge record identity and version, supporting-source identity and version, and a one-based character span.

**Expected result:** `sentence-pair-v1` produces retrieval units `F-A` and `F-B`. `fixed-72-v1` produces `F-A-72-1` through `F-A-72-4` and `F-B-72-1` through `F-B-72-2`. Every source fragment records `derived retrieval-side artifact; not a canonical knowledge collection member` as the collection-membership classification.

The command refuses to replace an existing `boundary-comparison.json`. If `boundary-comparison.json` already exists, stop before recording another boundary decision and inspect the existing Stage B evidence.

### Student Step 2 — Inspect the retrieval contract, source fragments, and provenance links

```bash
python -m json.tool reports/lab04/stage-b/boundary-comparison.json
```

Windows PowerShell:

```powershell
Get-Content reports/lab04/stage-b/boundary-comparison.json
```

Verify that:

- `retrieval_contract.declared fields` contains the text query, canonical knowledge collection version, retrieval unit and its boundary rule, retrieval configuration, ranked candidate output, evaluator-only expected result, relevance judging basis, designated human evaluator, and observation boundary.
- `canonical_knowledge_collection_version` identifies `course-seed-v1`.
- `canonical_knowledge_records` identifies `R-A` and `R-B` as supplied seed records and records `student_generated: false` and `student_approved: false` for both canonical knowledge records.
- `retrieval configuration roles` assigns `lexical retrieval` to the experiment-baseline retrieval configuration and `embedding-based retrieval` to the candidate retrieval configuration.
- No `operation_input` object contains an evaluator-only expected result.
- Every source fragment carries a stable retrieval identifier and a provenance link containing the canonical knowledge record identity, canonical knowledge record version, supporting-source identity, supporting-source version, and exact character span.

Compare the source fragments derived from `R-A` against the relevance judging basis of both evaluation cases. `F-A` preserves together the originating record identifier, record version, and exact supporting-passage location required by the relevance judging basis. No individual source fragment from `F-A-72-1` through `F-A-72-4` preserves all three required elements without reconstruction from another source fragment.

### Student Step 3 — Record the boundary decision

The student acts as the engineering team for the boundary decision. The deterministic laboratory command records the student-supplied selection and rationale and does not select a chunking configuration.

```bash
uv run learning-project lab04 record-boundary-decision \
  --report-dir reports/lab04 \
  --chunking-configuration-id sentence-pair-v1 \
  --rationale "The sentence-pair boundary rule preserves together the originating record identifier, record version, and exact supporting-passage location required by the relevance judging basis of Evaluation Case A and Evaluation Case B." \
  --by "<student-id>"
```

Windows PowerShell:

```powershell
uv run learning-project lab04 record-boundary-decision `
  --report-dir reports/lab04 `
  --chunking-configuration-id sentence-pair-v1 `
  --rationale "The sentence-pair boundary rule preserves together the originating record identifier, record version, and exact supporting-passage location required by the relevance judging basis of Evaluation Case A and Evaluation Case B." `
  --by "<student-id>"
```

The command writes `reports/lab04/stage-b/boundary-decision.yaml`. The boundary decision selects `source fragment under sentence-pair-v1` as the retrieval-unit definition for the declared evaluation cases and does not authorize a change to the canonical knowledge collection. The command refuses to replace an existing `boundary-decision.yaml`.

### Student Step 4 — Acquire the declared local embedding model once

```bash
uv run learning-project lab04 fetch-embedding-model --model-dir models/potion-base-8M
```

Windows PowerShell:

```powershell
uv run learning-project lab04 fetch-embedding-model --model-dir models/potion-base-8M
```

The command reads `representation_contract` from `cases/lab04/stage-c1-fixture.json`, prepares the local model directory, and records the local model provenance in `models/potion-base-8M/model-provenance.json`.

**Expected result:** the command prints the acquired embedding model `minishlab/potion-base-8M` at revision `bf8b056651a2c21b8d2565580b8569da283cab23`. Download waiting time is measured separately from the laboratory workload.

**If the local embedding model is unavailable** (network unreachable, insufficient disk space, or the declared revision `bf8b056651a2c21b8d2565580b8569da283cab23` cannot be resolved): stop before Student Step 5. Preserve `boundary-comparison.json`, `boundary-decision.yaml`, and the error output for diagnosis. Do not proceed to index preparation without the declared model. Record the stopping point and error in `reports/lab04/REPORT.md`.

If the local model directory records another model revision, the command stops instead of mixing two representation contracts. Remove that directory and repeat the command.

### Student Step 5 — Produce compatible retrieval-unit embeddings

```bash
uv run learning-project lab04 prepare-embeddings --report-dir reports/lab04
```

Windows PowerShell:

```powershell
uv run learning-project lab04 prepare-embeddings --report-dir reports/lab04
```

The command reads the chunking configuration recorded in `reports/lab04/stage-b/boundary-decision.yaml`, produces one retrieval-unit embedding for every retrieval unit that the recorded chunking configuration includes, and writes `reports/lab04/stage-c1/retrieval-unit-embeddings.json`. Every recorded retrieval-unit embedding carries the stable retrieval identifier and the provenance link of the represented retrieval unit, the representation version, the embedding dimension, and the embedding space.

**Expected result:** `sentence-pair-v1` produces one retrieval-unit embedding for `F-A` and one for `F-B`; every recorded retrieval-unit embedding has 256 coordinates and records embedding space `potion-base-8M@bf8b056651a2c21b8d2565580b8569da283cab23/course-static-embed-v1`.

The command stops without writing an artifact when the mandatory local embedding model is unavailable, and it names the acquisition command to run once. The command also stops when:

- the loaded model does not match the declared representation contract;
- a retrieval-unit embedding carries a different embedding dimension;
- a retrieval-unit embedding contains a non-finite coordinate.

### Student Step 6 — Prepare the vector index

```bash
uv run learning-project lab04 prepare-index --report-dir reports/lab04
```

Windows PowerShell:

```powershell
uv run learning-project lab04 prepare-index --report-dir reports/lab04
```

The command binds the compatible retrieval-unit embeddings and their associations into one versioned vector index. It obtains the canonical knowledge collection version from `reports/lab04/stage-c1/retrieval-unit-embeddings.json`, where Student Step 5 copied that value from `reports/lab04/stage-b/boundary-comparison.json` for the selected Stage B source fragments. In this laboratory implementation, the vector index's derived searchable state consists of the vectors in `reports/lab04/stage-c1/retrieval-unit-embeddings.json` together with the associations recorded in `reports/lab04/stage-c1/index-manifest.json`; the index manifest is the record of the vector index, not the vector index itself. The index manifest records:

- the index version;
- the collection-version binding;
- the chunking configuration;
- the embedding model and representation version;
- the required embedding dimension and embedding space;
- one metadata binding for every indexed retrieval unit.

The vector index is derived searchable state. The vector index is neither a canonical knowledge record nor a member of the canonical knowledge collection, and preparing the vector index does not authorize a change to the canonical knowledge collection.

**Expected result:** the index manifest records:

- the index version `vector-index-course-seed-v1`;
- the canonical knowledge collection version `course-seed-v1`;
- the chunking configuration `sentence-pair-v1`;
- two metadata bindings, one for `F-A` and one for `F-B`.

The command refuses to replace an existing `index-manifest.json` and refuses to index a set of retrieval units that does not cover the chunking configuration recorded in the boundary decision.

### Student Step 7 — Run the pre-use binding check

Run the pre-use binding check for both required retrieval configurations:

```bash
uv run learning-project lab04 check-index-bindings --report-dir reports/lab04 --required-retrieval-configuration-id required-course-seed-v1
uv run learning-project lab04 check-index-bindings --report-dir reports/lab04 --required-retrieval-configuration-id required-course-seed-v2
```

Windows PowerShell:

```powershell
uv run learning-project lab04 check-index-bindings --report-dir reports/lab04 --required-retrieval-configuration-id required-course-seed-v1
uv run learning-project lab04 check-index-bindings --report-dir reports/lab04 --required-retrieval-configuration-id required-course-seed-v2
```

**Expected result:** each check classifies the vector index and does not rebuild the index:

- the check for `required-course-seed-v1` prints that the vector index identified by index version `vector-index-course-seed-v1` is admissible and writes `reports/lab04/stage-c1/binding-check-required-course-seed-v1.json`;
- the check for `required-course-seed-v2` prints that the vector index identified by the same index version is stale for that required retrieval configuration, names `the canonical knowledge collection version` as the failed binding, states the rebuild condition, and writes `reports/lab04/stage-c1/binding-check-required-course-seed-v2.json`.

Verify the Stage C1 evidence:

```bash
uv run learning-project lab04 verify-stage-c1 --report-dir reports/lab04
```

Windows PowerShell:

```powershell
uv run learning-project lab04 verify-stage-c1 --report-dir reports/lab04
```

**Expected result:** `Laboratory 04 Stage C1 verification passed for vector-index-course-seed-v1.`

If the verification command returns a nonzero exit code, stop before Student Step 8. Preserve the retrieval-unit embeddings, the index manifest, the pre-use binding check records, and the error output for diagnosis.

### Student Step 8 — Execute both evaluation cases under all four retrieval configurations

Execute both evaluation cases under each of the four compared retrieval configurations. Use a fresh Stage C2 output directory; the command refuses to overwrite an existing output. Keep the four configuration names verbatim.

```bash
set -e
for case_id in 'Evaluation Case A' 'Evaluation Case B'; do
  for configuration_id in 'lexical retrieval' 'embedding-based retrieval' 'hybrid retrieval' 'lexical retrieval followed by embedding-based reranking'; do
    uv run learning-project lab04 execute-retrieval --report-dir reports/lab04 --model-dir models/potion-base-8M --case-id "$case_id" --configuration-id "$configuration_id"
  done
done
```

Windows PowerShell:

```powershell
$cases = @('Evaluation Case A', 'Evaluation Case B')
$configurations = @('lexical retrieval', 'embedding-based retrieval', 'hybrid retrieval', 'lexical retrieval followed by embedding-based reranking')
foreach ($case in $cases) {
    foreach ($configuration in $configurations) {
        uv run learning-project lab04 execute-retrieval --report-dir reports/lab04 --model-dir models/potion-base-8M --case-id "$case" --configuration-id "$configuration"
        if ($LASTEXITCODE -ne 0) { throw "Retrieval stopped for $case / $configuration" }
    }
}
```

Each command writes `reports/lab04/stage-c2/<evaluation-case>-<configuration>.json` with the text query, canonical knowledge collection version, ranking evidence, and ranked candidate output. A returned candidate records rank, stable retrieval identifier, provenance link, and score. An empty ranked candidate output is `[]`, not a relevance judgment.

**Retrieval rules** (from `cases/lab04/stage-c2-fixture.json`):

- `k = 1`, reranking candidate count at 2, ties broken by stable retrieval identifier ascending.
- **Lexical retrieval**: lowercases the text query and retrieval-unit text, extracts alphabetic tokens, excludes the fixture's excluded lexical function words, and counts distinct exact shared content words once; zero-overlap retrieval units do not enter the ranking.
- **Embedding-based retrieval**: encodes the text query with the declared local embedding model, performs exact cosine similarity search against every indexed retrieval-unit embedding, and checks the required bindings against the index manifest before scoring.
- **Hybrid retrieval**: produces a lexical ranking and an embedding-based ranking independently, normalizes each ranking's scores by dividing by the highest score in that ranking, and adds the normalized scores by stable retrieval identifier.
- **Lexical retrieval followed by embedding-based reranking**: takes at most the first two retrieval units from the lexical ranking as the bounded candidate set; an empty bounded candidate set produces an empty ranked candidate output.


**Inspect the observed ranked candidate outputs:**

```bash
uv run python -m json.tool reports/lab04/stage-c2/evaluation-case-a-hybrid-retrieval.json
uv run python -m json.tool reports/lab04/stage-c2/evaluation-case-b-lexical-retrieval-followed-by-embedding-based-reranking.json
```

Windows PowerShell:

```powershell
Get-Content reports/lab04/stage-c2/evaluation-case-a-hybrid-retrieval.json -Raw | ConvertFrom-Json | ConvertTo-Json -Depth 12
Get-Content reports/lab04/stage-c2/evaluation-case-b-lexical-retrieval-followed-by-embedding-based-reranking.json -Raw | ConvertFrom-Json | ConvertTo-Json -Depth 12
```

The observed ranked candidate output reports ranking evidence for the two declared cases, not relevance judgments and not evidence of general superiority of any retrieval mechanism.

Verify the Stage C2 evidence:

```bash
uv run learning-project lab04 verify-stage-c2 --report-dir reports/lab04 --model-dir models/potion-base-8M
```

Windows PowerShell:

```powershell
uv run learning-project lab04 verify-stage-c2 --report-dir reports/lab04 --model-dir models/potion-base-8M
```

**Expected result:** `Laboratory 04 Stage C2 verification passed for 8 outputs.`

If any command returns a nonzero exit code, stop before Student Step 9. Preserve the generated Stage C2 files, the preceding Stage B and Stage C1 evidence, and the error output for diagnosis. Do not overwrite an existing ranked candidate output or continue with a failed pre-use binding check.

### Student Step 9 — Record the relevance judgments

The student acts as the designated human evaluator in this step. The retrieval operation never receives the evaluator-only expected result: `record-relevance-judgments` reads the archived ranked candidate outputs, and `compute-retrieval-metrics` reads the recorded judgments and the evaluator-only expected results. Neither command passes evaluator-only material into the input of the retrieval operation.

The relevance judging basis for both evaluation cases reads: a retrieval unit must explain which data identify the originating record, the originating record version, and the exact location of the supporting passage.

Record one relevance judgment per returned retrieval unit and evaluation case. The recorded set must cover exactly the retrieval units returned by the compared configurations for that case: a missing returned retrieval unit and an extra identifier both stop the command. Each judgment carries a rationale.

Write the judgments to a local JSON file and run the command:

```bash
cat > judgments.json << 'JSON'
{
  "Evaluation Case A": [
    {"stable retrieval identifier": "F-B", "relevance judgment": "not relevant",
     "rationale": "F-B is the proposal-run receipt ... the relevance judging basis is not satisfied."}
  ],
  "Evaluation Case B": [
    {"stable retrieval identifier": "F-B", "relevance judgment": "not relevant",
     "rationale": "F-B identifies the model rather than the supporting passage ... the relevance judging basis is not satisfied."}
  ]
}
JSON
uv run learning-project lab04 record-relevance-judgments --report-dir reports/lab04 --judgments judgments.json --evaluator "your name, designated human evaluator"
```

Windows PowerShell (the `.NET` call writes UTF-8 without a byte-order mark):

```powershell
$json = @'
{
  "Evaluation Case A": [
    {"stable retrieval identifier": "F-B", "relevance judgment": "not relevant",
     "rationale": "F-B is the proposal-run receipt ... the relevance judging basis is not satisfied."}
  ],
  "Evaluation Case B": [
    {"stable retrieval identifier": "F-B", "relevance judgment": "not relevant",
     "rationale": "F-B identifies the model rather than the supporting passage ... the relevance judging basis is not satisfied."}
  ]
}
'@
[System.IO.File]::WriteAllText("$PWD\judgments.json", $json, [System.Text.UTF8Encoding]::new($false))
uv run learning-project lab04 record-relevance-judgments --report-dir reports/lab04 --judgments judgments.json --evaluator "your name, designated human evaluator"
```

The command writes `reports/lab04/stage-c3/relevance-judgments.json` and refuses to overwrite an existing file. Replace the ellipsis placeholders in each rationale with the complete reasoning that applies the declared relevance judging basis to the specific returned retrieval unit.

The reference above reflects the archived real-model execution, where the only returned retrieval unit in each case was `F-B`. The exact identifier set in your run depends on the ranked candidate outputs produced in Student Step 8; supply a judgment for every returned retrieval unit and for no other identifier.

### Student Step 10 — Compute and inspect the retrieval metrics

```bash
uv run learning-project lab04 compute-retrieval-metrics --report-dir reports/lab04 --model-dir models/potion-base-8M
```

Windows PowerShell:

```powershell
uv run learning-project lab04 compute-retrieval-metrics --report-dir reports/lab04 --model-dir models/potion-base-8M
```

The command re-verifies the eight ranked candidate outputs before computing. A tampered Stage C2 output stops the step. The command writes `reports/lab04/stage-c3/retrieval-metrics.json` with per-case and aggregate entries. Each entry states the ranked candidate output, the judged returned retrieval units, and both metrics with an explicit numerator and denominator. An empty ranked candidate output records `precision@1` as `undefined` with its reason and `recall@1` as `0 of 1`.

**Metric definitions:**

- `precision@k`: numerator is the number of the first `k` returned retrieval units judged relevant; denominator is the number of returned retrieval units in those first `k` positions. `precision@k` is **undefined** rather than zero when the ranked candidate output contains no retrieval unit.
- `recall@k`: numerator is the number of reviewed relevant retrieval units present among the first `k` returned retrieval units; denominator is the total number of reviewed relevant retrieval units in the evaluator-only expected result. `recall@k` remains defined when the ranked candidate output is empty.

**Aggregation rule:** the aggregate counts judged returned retrieval units across both evaluation cases. An empty ranked candidate output contributes no judged returned retrieval unit to the precision denominator while the reviewed relevant retrieval unit in the evaluator-only expected result still enters the recall denominator.

**Archived reference values** (real-model execution with the declared local embedding model at `k=1`):

| Retrieval configuration | `precision@1` (aggregate) | `recall@1` (aggregate) |
|---|---|---|
| lexical retrieval | 0 relevant of 1 judged returned = 0.00 | 0 of 2 reviewed relevant = 0.00 |
| embedding-based retrieval | 0 relevant of 2 judged returned = 0.00 | 0 of 2 reviewed relevant = 0.00 |
| hybrid retrieval | 0 relevant of 2 judged returned = 0.00 | 0 of 2 reviewed relevant = 0.00 |
| lexical retrieval followed by embedding-based reranking | 0 relevant of 1 judged returned = 0.00 | 0 of 2 reviewed relevant = 0.00 |

In the archived execution, Evaluation Case A produced an empty ranked candidate output under the lexical and reranked configurations, so their `precision@1` is `undefined` rather than `0.00` for that case. Report the values from your own run; they depend on the ranked candidate outputs and the relevance judgments you recorded.

### Student Step 11 — Measure the operational evidence

```bash
uv run learning-project lab04 measure-operational-evidence --report-dir reports/lab04 --model-dir models/potion-base-8M --runs 3
```

Windows PowerShell:

```powershell
uv run learning-project lab04 measure-operational-evidence --report-dir reports/lab04 --model-dir models/potion-base-8M --runs 3
```

The command re-executes both declared text queries under each configuration in a temporary copy of the prepared evidence and records the five measured items in `reports/lab04/stage-c3/operational-evidence.json`:

- prepared-index build or update cost — one Stage C1 index preparation; no rebuild is measured here.
- query latency — wall-clock seconds for executing both declared text queries once per run, averaged over 3 runs in one process.
- query cost — encodes per execution under the declared encoder.
- resource consumption — local model reuse in one process; no network access.
- execution failures — `WorkflowError` outcomes raised while executing both declared text queries.

Each item records its own measurement boundary. No measurement from this list enters the numerator or denominator of `precision@1` or `recall@1`. Report the measured values from your own host; they are measurements, not relevance.

### Student Step 12 — Record one bounded configuration decision

State the decision with a rationale argued from the recorded metrics and the measured operational evidence.

```bash
uv run learning-project lab04 record-configuration-decision --report-dir reports/lab04 \
  --selected-configuration "lexical retrieval" --decided-by "your name, engineering team" \
  --rationale "Under the two declared development evaluation cases at configured result count k=1 and the executed model, no compared configuration returned the reviewed relevant retrieval unit: aggregate recall@1 is 0 of 2 for every configuration ... the evidence does not support adopting the embedding-based candidate configuration in place of the lexical experiment baseline, so the bounded decision retains the experiment-baseline lexical retrieval configuration for these declared cases only."
```

Windows PowerShell:

```powershell
uv run learning-project lab04 record-configuration-decision --report-dir reports/lab04 `
  --selected-configuration "lexical retrieval" --decided-by "your name, engineering team" `
  --rationale "Under the two declared development evaluation cases at configured result count k=1 and the executed model, no compared configuration returned the reviewed relevant retrieval unit: aggregate recall@1 is 0 of 2 for every configuration ... the evidence does not support adopting the embedding-based candidate configuration in place of the lexical experiment baseline, so the bounded decision retains the experiment-baseline lexical retrieval configuration for these declared cases only."
```

The command requires a substantive rationale and writes `reports/lab04/stage-c3/configuration-decision.json`. The configuration decision is bounded to:

- Evaluation Case A and Evaluation Case B;
- canonical knowledge collection version `course-seed-v1`;
- the `sentence-pair-v1` retrieval-unit boundary;
- the declared relevance judging basis;
- `k = 1`.

The decision does not:

- establish the quality of the candidate concept definition produced downstream;
- establish that the complete user workflow achieves its intended result;
- authorize any change to the canonical knowledge collection.

The selected configuration in your run follows from your own recorded metrics and operational evidence. If your ranked candidate outputs and relevance judgments differ from the archived reference, supply the configuration and rationale that the evidence supports.

### Student Step 13 — Verify and stop

```bash
uv run learning-project lab04 verify-stage-c3 --report-dir reports/lab04 --model-dir models/potion-base-8M
```

Windows PowerShell:

```powershell
uv run learning-project lab04 verify-stage-c3 --report-dir reports/lab04 --model-dir models/potion-base-8M
```

**Expected result:** `Laboratory 04 Stage C3 verification passed for 8 metric entries.` The verifier independently recomputes the metric arithmetic from the recorded relevance judgments and the verified eight ranked candidate outputs and compares the result with the recorded retrieval metrics. The verifier records no relevance judgment of its own.

If the command returns a nonzero exit code, stop before submitting.

Preserve:

- the generated Stage C3 files;
- the Stage C2 ranked candidate outputs;
- the Stage B and Stage C1 evidence;
- the error output for diagnosis.

Do not:

- overwrite recorded judgments or metrics;
- silently delete evidence to force a rerun;
- interpret a retrieval metric beyond its declared numerator, denominator, evaluation cases, and observation boundary.

## Final verification

Run `verify-stage-c3` as described in Student Step 13. The laboratory is complete when the command prints `Laboratory 04 Stage C3 verification passed for 8 metric entries.`

## Submission artifacts

See [LABORATORY_STANDING_RULES.md](../../LABORATORY_STANDING_RULES.md) for the standing submission rules.

Laboratory-specific artifacts:

- `reports/lab04/stage-b/boundary-comparison.json`
- `reports/lab04/stage-b/boundary-decision.yaml`
- `reports/lab04/stage-c1/retrieval-unit-embeddings.json`
- `reports/lab04/stage-c1/index-manifest.json`
- Two pre-use binding check records under `reports/lab04/stage-c1/`
- Eight ranked candidate output files under `reports/lab04/stage-c2/`
- `reports/lab04/stage-c3/relevance-judgments.json`
- `reports/lab04/stage-c3/retrieval-metrics.json`
- `reports/lab04/stage-c3/operational-evidence.json`
- `reports/lab04/stage-c3/configuration-decision.json`
- `reports/lab04/REPORT.md` (completed from the supplied template)

## Control questions

1. Why does the `sentence-pair-v1` boundary rule satisfy the relevance judging basis of both evaluation cases while no individual source fragment from `fixed-72-v1` does?
2. What does the index manifest record, and why does preparing the vector index not authorize a change to the canonical knowledge collection?
3. Why is `precision@1` undefined rather than zero when a retrieval configuration returns no retrieval unit in a given evaluation case?
4. When a ranked candidate output is empty, why does the reviewed relevant retrieval unit in the evaluator-only expected result remain in the `recall@1` denominator while the empty output contributes no judged returned retrieval unit to the `precision@1` denominator under the aggregation rule?
5. What is the decision boundary of the recorded configuration decision, and what claims does that decision not authorize?

## Optional extension

Repeat Student Steps 1–3 in a fresh `reports/lab04-fixed72` directory, changing each `--report-dir` argument accordingly.

- In Student Step 3, set `--chunking-configuration-id fixed-72-v1` and update `--rationale` to justify that selection.
- Run Student Steps 5–8 against `reports/lab04-fixed72`, complete Stage C2 verification, and compare the resulting ranked candidate outputs with the `sentence-pair-v1` run.
- Explain how the boundary rule choice changes the retrieval-unit set, and why the supplied `sentence-pair-v1` evaluator-only expected results cannot evaluate the `fixed-72-v1` outputs.

Stop before Student Step 9 unless separately reviewed evaluation cases and their evaluator-only expected results declare `fixed-72-v1` as the retrieval-unit definition of those cases. At that stopping point, do not:

- record relevance judgments;
- compute retrieval metrics;
- record a configuration decision;
- run Stage C3 verification.
