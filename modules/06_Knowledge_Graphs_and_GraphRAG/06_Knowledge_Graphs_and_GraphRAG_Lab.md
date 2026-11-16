# Module 06: Knowledge Graphs and GraphRAG — Laboratory

> **Status:** Ready for Students — English laboratory and Ukrainian translation approved by the instructor on 2026-11-10

## Goal

The goal of this laboratory is:

1. Closure of the gap left open after retrieval-ranked evidence on the prerequisite path covered by Module 06 theory:
   - ranked **source fragments** do not store which concept depends on which other concept;
   - a bounded **graph path** preserves prerequisite direction and support references without treating **graph traversal** as **logical inference**.
2. Execution of the **model-backed prerequisite-explanation operation** on that path under paired evidence-preparation configurations (with and without **graph expansion**), producing a **generated prerequisite explanation** or a **refusal**.
3. Evaluation of those generated outcomes as results of the completed path segment, with separate evidence-coverage and response judgments and one **bounded configuration decision** on the exposed development cases.

## Tasks

- Inspect model-proposed prerequisite connections against course-supplied source fragments, resolve **concept mentions**, complete human **semantic review**, authorize accepted storage, and compile the accepted graph in the disposable collection.
- Execute bounded outgoing `requires` queries, inspect returned paths and the missing direct edge, and interpret the matching small **Cypher** pattern without installing a graph database.
- Prepare paired **supplied source evidence** and **bounded model requests** with and without **graph expansion**, including duplicate-only discovery and unresolved-target fallback under the declared **context budget**.
- Freeze the **shared experiment protocol**, run the **model-backed prerequisite-explanation operation** under both configurations on two development cases, and preserve complete observed outcomes.
- Act separately as **human evaluator** and **engineering team**: record independent evidence and response judgments, inspect configuration-local **rubric pass rates** and **acceptance conditions**, and record one **bounded configuration decision** only when comparison evidence is complete.
- Apply the representation and review boundary to one public or synthetic connection from another study area without mutating the teaching collection.
- Complete the seven-checkpoint Ukrainian source report, bind evidence to the exact final branch head, and prepare the standalone Microsoft Teams report.

## Expected result

After completing the laboratory, the student holds an inspectable evidence path containing:

- `student/lab06-collection/accepted.json` and `reports/lab06/graph-preparation/graph.json` — accepted concepts, occurrence associations, relations and the compiled graph;
- `reports/lab06/graph-query/paths-1.json`, `paths-2.json` and `direct-edge.json` — bounded path and missing-direct-edge observations;
- `reports/lab06/evidence-preparation/evidence-preparation.json` and `policy-probes.json` — paired discovery, admission and **bounded model requests**;
- `reports/lab06/generation/protocol.json` and four run directories under `reports/lab06/generation/runs/` — actual **generated prerequisite explanations** or **refusals** with provider captures;
- `reports/lab06/judgments.json`, `comparison.json` and, when complete, `decision.json` — independent judgments, rates, condition results and the scoped decision or honest no-decision record;
- the transfer checkpoint prose and seven screenshots under `reports/lab06/screenshots/`;
- `reports/lab06/verification-report.json` — final verification bound to the exact branch head;
- `reports/lab06/submission/REPORT.md` — the standalone narrative report with the reached checkpoint images embedded.

The evidence does not authorize deployment, a held-out generalization claim, a write to a personal vault, or a claim that incomplete comparison evidence still yields a configuration decision.

## Expected competencies

After completing the laboratory, the student can:

- separate **structural validation** from human source-support judgment for prerequisite relations;
- compile and verify an accepted graph without inventing edges or concept identities;
- interpret bounded **graph paths**, extension status and a missing stored direct edge without **logical inference**;
- distinguish discovery through **graph expansion** from admission into **supplied source evidence** under a **context budget**;
- construct three-field **bounded model requests** while excluding graph paths and evaluator-only material;
- preserve and inspect **generated prerequisite explanations** and **refusals** under two evidence-preparation configurations;
- apply the **Prerequisite explanation check** or the **Refusal check** at the response-level observation boundary;
- calculate configuration-local **rubric pass rates**, evaluate frozen **acceptance conditions**, and record a **bounded configuration decision** only within its authority;
- complete the report route, including one bounded transfer and commit-bound verification.

## Prerequisites

- Laboratories 01–05 completed on personal branches.
- The current `training-project` release synchronized and its dependencies installed with the project instructions.
- Authenticated AGY access from Laboratory 02.
- AGY model catalogue containing `gemini-3.8-flash-low` and sufficient no-cost AGY quota for four generation runs.
- A fork of the course repository with permission to create and push a personal branch.
- A Windows workstation with a local administrator account, or a Linux or macOS workstation with equivalent rights to install project dependencies and write under the repository tree. Course laboratories assume administrator rights on Windows and are not adapted for limited Windows accounts.

## Starting state

The course supplies:

- accepted seed **concept records**, designated teaching source fragments, extraction observation and graph-preparation fixtures under `cases/lab06/`;
- disposable collection path `student/lab06-collection/`, declared graph schema and project commands;
- evidence-preparation fixtures, evaluation cases, evaluator-only references, one 250-character **context budget**, one generator configuration, rubric checks and predeclared **acceptance conditions**;
- the Laboratory 06 report fixture `fixtures/lab06/REPORT.md`.

Create the personal Laboratory 06 branch from the completed Laboratory 05 branch. Initialize the source report and screenshot directory before running any Laboratory 06 operation. Supplied rankings and captured extraction proposals are teaching inputs, not fresh retrieval measurements or acceptance decisions.

## Steps

### Student Step 1 — Create the branch and initialize the report route
Start from the repository root:

Windows PowerShell:

```powershell
git switch lab05/<student-id>
git switch -c lab06/<student-id>
cd .\training-project
New-Item -ItemType Directory -Force reports/lab06/screenshots | Out-Null
if (-not (Test-Path reports/lab06/REPORT.md)) { Copy-Item fixtures/lab06/REPORT.md reports/lab06/REPORT.md }
```

Linux and macOS:

```bash
git switch lab05/<student-id>
git switch -c lab06/<student-id>
cd training-project
mkdir -p reports/lab06/screenshots
test -f reports/lab06/REPORT.md || cp fixtures/lab06/REPORT.md reports/lab06/REPORT.md
```

Record the fork URL, personal branch `lab06/<student-id>`, and provisional completion state in `reports/lab06/REPORT.md`. Preserve every supplied heading. The seven relative screenshot links are:

- `01-reviewed-graph.png`
- `02-bounded-paths.png`
- `03-evidence-preparation.png`
- `04-observed-outcomes.png`
- `05-comparison-decision.png`
- `06-transfer-review.png`
- `07-final-verification.png`

Capture each of `01`–`05` immediately after the corresponding graph, query, evidence-preparation, generation, and decision checkpoints named in the later steps. Do not create placeholder images. Every real screenshot must show the operating-system or GitHub account and the system date.

**Expected result:** the current branch is `lab06/<student-id>`, the source report exists from the fixture, and `reports/lab06/screenshots/` exists before graph preparation.

## Reviewed graph preparation

The course supplies `cases/lab06/graph-preparation.json` with the following accepted **concept records**:

- `C-RET` — **Embedding-based retrieval**.
- `C-QUERY` — **Query embedding**.
- `C-MODEL` — **Embedding model**.

The course supplies three **source fragments**:

- `F-1`, `S-TEACH/v1`, sentence 1: “In this teaching route, understanding embedding-based retrieval requires understanding a query embedding.”
- `F-2`, `S-TEACH/v1`, sentence 2: “In this teaching route, understanding a query embedding requires understanding the embedding model that produces the query embedding.”
- `F-3`, `S-AMBIG/v1`, sentence 1: “The embedding is needed before the next exercise.”

The fragments reproduce the course-authored teaching notes from the theory, not external quotations. The phrase “In this teaching route” qualifies the prerequisite claims; the claims do not establish a universal learning order.

`cases/lab06/extraction-observation.json` preserves a real model-backed **knowledge extraction** request, the complete observed response, the parsed proposals and run metadata. The course captured the response with `agy`, model `gemini-3.8-flash-low`; the student replays the captured proposals without a new model call or charge for graph preparation. The captured response is not an acceptance decision.

The course preparation fixture distinguishes the following proposal origins:

- `P-1` and `P-2` preserve the observed endpoint identities, direction, support references and qualification. The course assigns local proposal/relation identifiers and source-occurrence references.
- `P-3` deliberately reverses the `F-1` claim. The reversed proposal is a course-authored negative probe, not observed model output.
- `P-4` proposes a connection from the ambiguous occurrence in `F-3` toward **embedding model** (`C-MODEL`), referenced by `M-4` in `F-2`. The unresolved-endpoint proposal is another course-authored probe, not observed model output.

The course also supplies **concept mention** locations and proposed matches for **entity resolution**. The student checks every match against the fragment and concept description. String similarity and a proposed identifier do not establish concept identity. The bounded exercise uses existing matches and an unresolved outcome; the exercise does not implement creating a new concept record.

### Student Step 2 — Prepare and inspect the proposals

From `AI_Systems_Design/training-project`, run the same command in Windows PowerShell or a Linux/macOS terminal:

```text
uv run learning-project lab06 prepare-graph-review --output reports/lab06/graph-preparation/review.json
```

The command creates the preparation directory and `review.json`, containing the exact supplied input, mechanical `proposal_structure` results and empty human-review entries. Open the JSON file in the editor. Inspect `reviewed_input`, including `graph_schema`, concept descriptions, fragment provenance, mentions and proposals. The `requires` direction starts at the dependent concept and ends at the prerequisite concept.

**Expected structural results:**

- `P-1`, `P-2` and `P-3` — `conforms`: endpoint types and support references satisfy the graph schema.
- `P-4` — `unresolved endpoint`: unresolved **concept mention** `M-6` supplies no accepted starting endpoint.
- Every human judgment remains `pending`; `reviewer` is empty and `authorize` is `false`.

Structural conformance does not establish source support. In particular, the conforming reversed claim still requires rejection by the human reviewer. If preparation fails or the output already exists, stop and inspect the existing evidence and error; do not overwrite an earlier result.

### Student Step 3 — Resolve occurrences and review each connection

In the editor, change only `mention_reviews`, `relation_reviews`, `reviewer` and `authorize` in `review.json`. Preserve `reviewed_input` and `proposal_structure` exactly. The source-occurrence offsets are zero-based character positions with the ending position excluded; each occurrence retains the original wording.

For every `mention_reviews` entry, the student records one outcome and a source-based `rationale`:

- `match` — set `concept_id` to the existing accepted concept identifier after checking the source context and the concept description.
- `unresolved` — leave `concept_id` as JSON `null` and explain why the available context does not establish an identity.

For example, after checking `F-1` and `C-RET`, the `M-1` entry can read:

```json
{"outcome": "match", "concept_id": "C-RET", "rationale": "F-1 names embedding-based retrieval as the dependent concept in the teaching route."}
```

The student inspects the remaining occurrences separately:

1. `M-2`, `M-3` and `M-5` refer to separate occurrences of **query embedding**, including two occurrences in `F-2`. Matching the occurrences to `C-QUERY` creates no duplicate concept records.
2. `M-4` names **embedding model** in `F-2`; the context identifies the model producing the query embedding.
3. `M-6` names “embedding” in `F-3`. The source does not identify a unique accepted concept and does not justify a new concept record merely named “Embedding”. The unresolved outcome supplies no accepted endpoint.

For every `relation_reviews` entry, the student records `decision` and a source-based `rationale`:

- `accept` — both endpoints are resolved and the cited source supports the exact prerequisite direction and qualification.
- `reject` — both endpoints are resolved, but the cited source does not support the proposed claim.
- `blocked` — an endpoint remains unresolved; the affected connection cannot reach semantic acceptance or storage.

The student checks `P-1` against `F-1` and `P-2` against `F-2`. The student rejects `P-3` because `F-1` does not state the reversed direction, without inferring universal impossibility of the reversed prerequisite. The student records `P-4` as blocked by `M-6`; the unresolved item does not prevent independent accepted connections from continuing.

Only after completing every entry, the student sets `reviewer` to the student's identifier and `authorize` to JSON `true`, authorizing the exact accepted matches and relations in the reviewed document. Do not copy another person's authorization. Save the completed document before invoking the writer.

### Student Step 4 — Store accepted changes

Windows PowerShell and Linux/macOS:

```text
uv run learning-project lab06 apply-graph-review --review reports/lab06/graph-preparation/review.json --collection student/lab06-collection
```

The authorized writer checks exact input identity, completed item judgments, endpoint references and explicit authorization, then creates `student/lab06-collection/accepted.json`. The snapshot contains the existing concept records, source fragments, accepted occurrence associations, accepted relations and the exact review used for writing. The writer does not judge source support and does not override a human decision.

**Expected result for the reviewed teaching inputs:**

- Three accepted concept identities, not one record per occurrence.
- Five accepted occurrence associations; `M-6` remains unresolved in the retained review.
- `R-1`: `C-RET` requires `C-QUERY`, supported by `F-1`.
- `R-2`: `C-QUERY` requires `C-MODEL`, supported by `F-2`.
- No accepted relation from rejected `P-3` or blocked `P-4`.

An incomplete review, invalid reference, changed input or missing authorization stops writing. An existing `accepted.json` is not replaced. Stop on a nonzero exit code and preserve the review and error output. Do not edit the accepted snapshot to make a later check pass.

### Student Step 5 — Compile and verify the graph

Windows PowerShell and Linux/macOS:

```text
uv run learning-project lab06 compile-graph --collection student/lab06-collection --output reports/lab06/graph-preparation/graph.json
uv run learning-project lab06 verify-graph --collection student/lab06-collection --graph reports/lab06/graph-preparation/graph.json
```

Inspect `graph.json` in the editor alongside the verification output. Graph compilation creates three concept nodes and the two accepted directed edges, retaining `relation_record_id`, support-fragment references and the teaching-route qualification. The source fragments retain source-material identity, version and location, and the occurrence associations remain inspectable. Compilation neither changes the collection nor creates a direct edge from `C-RET` to `C-MODEL`.

**Expected message:** `Graph verification passed for 3 nodes and 2 edges; source support remains a human judgment.` The verifier reconstructs accepted storage from the retained review and compares the complete derived graph. The structural check does not authenticate a human signature, reassess source meaning or prove general domain correctness.

After successful verification, capture `01-reviewed-graph.png`, showing the two edge directions, relation-record and support references, and the successful verification message. Preserve the completed review, accepted snapshot and graph for the report route. If verification fails, stop before graph queries and preserve the error. The student path ends at the compiled accepted graph.

## Bounded graph queries

The student executes a read-only **graph query**, inspects the returned **graph paths**, and distinguishes an uninspected continuation from a missing stored direct edge. Module 06 Section 3 supplies the query and interpretation rules. The starting state is the successfully verified graph from Student Step 5:

- Accepted collection: `student/lab06-collection/accepted.json`.
- Compiled graph: `reports/lab06/graph-preparation/graph.json`.
- **Embedding-based retrieval**: `C-RET`, the dependent starting concept.
- **Query embedding**: `C-QUERY`, the intermediate prerequisite concept.
- **Embedding model**: `C-MODEL`, the prerequisite reached through `C-QUERY`.

The commands check the compiled graph against the exact accepted collection before querying. The executable graph retains collection version `lab06-teaching-v1`; Module 06's `G-TEACH/v1` names the stipulated teaching graph, not a database execution or a new source-material version. The commands read the graph and collection, write separate query records, and make no model call. The path ends before evidence preparation or explanation generation.

### Student Step 6 — Compare one-edge and two-edge requests

The student runs the following commands from `AI_Systems_Design/training-project`. Windows PowerShell and Linux/macOS use the same commands:

```text
uv run learning-project lab06 query-paths --collection student/lab06-collection --graph reports/lab06/graph-preparation/graph.json --start C-RET --max-edges 1 --output reports/lab06/graph-query/paths-1.json
uv run learning-project lab06 query-paths --collection student/lab06-collection --graph reports/lab06/graph-preparation/graph.json --start C-RET --max-edges 2 --output reports/lab06/graph-query/paths-2.json
```

Each command creates the output directory when necessary. The course query evaluator implements **graph traversal** under the following declared settings:

- Start at `C-RET`; follow only outgoing `requires` edges, from dependent concept to prerequisite concept.
- Return every matching path of at least one edge within `max_edges`, not only paths reaching the maximum length. The teaching command supports maximum lengths of one or two edges.
- Do not extend a path to a node already present in the same path. Distinct paths may reach the same endpoint.
- Stop extending at the maximum length or when no eligible outgoing edge remains. The small teaching graph needs no additional resource cutoff; a depth bound alone does not bound branching in an arbitrary graph.
- Order results by edge count, then concept-identifier sequence; use relation-record-identifier sequence only to break remaining ties. The ordering does not rank prerequisite importance.

Open both JSON outputs in the editor. Inspect `collection_version`, `request`, `start_status` and every `paths` entry. In each path, `concept_ids` preserves the node sequence; `relation_record_ids`, `support_fragment_ids` and `qualifications` preserve the connecting edges in the same order. Each nested support list belongs to the corresponding edge, not to a newly inferred endpoint relation. Use the retained fragment identifiers to inspect source wording and provenance in `graph.json`.

**Expected results for the accepted teaching graph:**

- `paths-1.json`: `start_status` is `present`; one row contains `C-RET → C-QUERY`, relation record `R-1`, support `F-1`, and qualification `In this teaching route`.
- `paths-2.json`: `start_status` is `present`; two rows contain `C-RET → C-QUERY` with `R-1`, and `C-RET → C-QUERY → C-MODEL` with `R-1, R-2`. The two-edge path preserves support lists `[F-1], [F-2]` and the teaching-route qualification for both edges.
- `paths-1.json`, one-edge row: `extension_status` is `depth limit: continuation not inspected`.
- `paths-2.json`, one-edge row: `extension_status` is `extended`, because the two-edge request inspects the continuation through `R-2`.
- The two-edge row in `paths-2.json` also ends at the depth limit. The status does not assert either presence or absence of outgoing edges from `C-MODEL`; the query did not inspect a third step.

Path length counts edges: the two-edge path has three nodes. An empty `paths` list with `start_status: absent` differs from an empty list for a present starting node with no matching outgoing edge. For the prescribed requests, stop if a command fails, a starting node is absent, or the observed rows differ from the expected rows. Preserve the error and input files; do not edit accepted records or query results to manufacture agreement. Existing output files are never overwritten.

### Student Step 7 — Check for a direct outgoing requires edge from C-RET to C-MODEL

The student tests whether the stored graph directly connects `C-RET` to `C-MODEL`. Windows PowerShell and Linux/macOS:

```text
uv run learning-project lab06 inspect-direct-edge --collection student/lab06-collection --graph reports/lab06/graph-preparation/graph.json --start C-RET --target C-MODEL --output reports/lab06/graph-query/direct-edge.json
```

Open `direct-edge.json` and inspect the complete outgoing `requires` set from `C-RET`, not only the matching endpoint list. Expected results are:

- `start_status` and `target_status`: `present`.
- `outgoing_edges`: one edge from `C-RET` to `C-QUERY`, preserving `R-1`, support `F-1` and the teaching-route qualification.
- `matching_edges`: empty; `direct_edge_present`: `false`.

The separate inspection establishes that the direct `C-RET → C-MODEL` edge is absent from the declared graph. The two-edge path through `C-QUERY` remains present. Neither result establishes that a prerequisite is absent from the subject domain. **Graph traversal** reports stored connections; traversal alone supplies no **logical inference** rule authorizing a new direct prerequisite assertion or a classification claim. No query writes an inferred edge or a new accepted relation.

If either endpoint is absent or the outgoing set differs from the accepted teaching graph, stop and inspect the identifiers and verified starting state before interpreting the result.

### Student Step 8 — Interpret a **Cypher** path pattern and capture `02-bounded-paths.png`

The student reads the following **Cypher** pattern alongside `paths-2.json`:

```cypher
MATCH p = (start:Concept {id: 'C-RET'})-[:requires*1..2]->(prerequisite:Concept)
WHERE all(n IN nodes(p) WHERE single(m IN nodes(p) WHERE m = n))
RETURN [n IN nodes(p) | n.id] AS concept_ids,
       [r IN relationships(p) | r.relation_record_id] AS relation_record_ids
ORDER BY length(p), concept_ids
```

The pattern is the readable query from Module 06 Section 3.3, not code executed by the project CLI. No graph database installation or Cypher execution is required. The course query evaluator implements the same bounded structural request and additionally retains support references, qualifications and extension status.

In the report notes, the student explains the following correspondences against the observed outputs:

1. `MATCH` selects the `Concept` node `C-RET`; `-[:requires*1..2]->` follows one or two outgoing prerequisite edges. Changing the range to `*1..1` corresponds to the one-edge request.
2. The `WHERE` condition excludes repeated nodes within a path without globally discarding other routes to an endpoint.
3. `RETURN` preserves the intermediate node and connecting relation records. Returning only `C-RET` and `C-MODEL` would hide `C-QUERY`, `R-1` and `R-2`.
4. The one-edge depth limit leaves the continuation uninspected; the separate direct-edge inspection establishes only a missing stored direct edge. Neither observation authorizes accepted-state changes or domain-level absence claims.

Finally, run the existing graph verifier on Windows PowerShell or Linux/macOS:

```text
uv run learning-project lab06 verify-graph --collection student/lab06-collection --graph reports/lab06/graph-preparation/graph.json
```

Continue only after the three query records match the expected results and the verifier reports `Graph verification passed for 3 nodes and 2 edges; source support remains a human judgment.` The verifier checks graph/collection consistency, not the student's interpretation or source support. Capture `02-bounded-paths.png`, showing the two-edge node sequence, `R-1, R-2` and the successful verification message. Preserve the three query JSON files and interpretation notes for the report route. No source text is assembled into a model request at the end of the path.

## Paired evidence preparation

The student prepares **supplied source evidence** with and without **graph expansion**, then inspects whether discovered text actually enters a **bounded model request**. Module 06 Section 4 supplies the discovery rules; Module 05 Sections 2–3 supply the admission and request boundaries. Successful preparation does not establish answer quality.

Continue from the verified Student Step 8 state. The commands use:

- Accepted collection: `student/lab06-collection/accepted.json`.
- Compiled graph: `reports/lab06/graph-preparation/graph.json`.
- Main teaching inputs: `cases/lab06/evidence-preparation.json`.
- Non-generation policy probes: `cases/lab06/evidence-policy-probes.json`.

Both files name **Embedding-based retrieval** (`C-RET`) as the target. **Query embedding** (`C-QUERY`) and **Embedding model** (`C-MODEL`) retain the accepted prerequisite identities. Fragment text and accepted associations come from the prepared collection; the course supplies the initial rankings, not a new **retrieval operation**. The main inputs are preparation inputs, not yet complete **evaluation cases**. The policy probes add no live-generation obligation.

### Student Step 9 — Prepare paired **supplied source evidence** and **bounded model requests**

The student runs the following command from `AI_Systems_Design/training-project`. Windows PowerShell and Linux/macOS use the same command:

```text
uv run learning-project lab06 prepare-evidence --collection student/lab06-collection --graph reports/lab06/graph-preparation/graph.json --output reports/lab06/evidence-preparation/evidence-preparation.json
```

The command creates the output directory when necessary and writes one preparation record containing both configurations for each teaching input. The course fixes a **context budget** of 250 Unicode characters of fragment text, including spaces and punctuation. Only fragment text contributes to the count; request metadata contributes no characters. The measured strings occupy 105 characters for `F-1`, 133 for `F-2`, and 49 for `F-3`. The limit is declared before generation, differs from the theory's illustrative 238-character limit, and is not a model-token allowance.

The application performs the following operations in dependency order for `with graph expansion`:

1. **Entry-node lookup** follows accepted `mention_associations` from original fragment identifiers to accepted **concept records**. The application retains records whose `primary_label` exactly equals `target_label`, then counts distinct matching node identifiers. Exactly one match permits expansion; zero or several matches record `unresolved` and preserve original candidates without expansion. The application performs no new concept matching.
2. **Graph expansion** follows outgoing `requires` edges for at most two edges under Student Step 6's path and ordering rules. The application retains inspected paths and expanded node identifiers outside the **bounded model request**; the graph remains unchanged.
3. Support-fragment lookup follows the inspected edges' relation-record references to supporting fragment identifiers and loads the corresponding fragment text. The application does not treat a path as source text or a supporting-fragment reference as **provenance-link resolution**.
4. Candidate assembly preserves original order, appends fragments in deterministic path/relation/support order, and removes repeated fragment identifiers. Different identifiers remain distinct even when text overlaps. No additional fragment receives an invented **similarity score**.
5. **Retrieval-unit selection** checks **provenance-link resolution** before **context-budget fit**, admits complete **retrieval units**, records the first failed criterion, and continues to later candidates. Resolution checks the locator and exact text against the course-supplied source-fragment snapshot in `graph-preparation.json`; no external source lookup or new source-support judgment is claimed.
6. **Context construction** builds the three-field **bounded model request** from admitted **retrieval units** without executing the model. The configuration `without graph expansion` applies the same admission and request rules to original candidates alone.

Open `evidence-preparation.json`. Within each `inputs` entry, inspect the two labelled `configurations` entries. Each configuration records:

- `entry_node_lookup`: the lookup status and distinct matching node identifiers.
- `expanded_node_ids`: the starting node and nodes reached by expansion.
- `paths`: inspected structural paths, outside the **bounded model request**.
- `discovered_fragment_ids`: distinct fragment identifiers found through support references.
- `added_fragment_ids`: discovered identifiers not already present among original candidates.
- `candidate_fragment_ids`: the final original-order-first assembly.
- `selection_record`: ordered candidates, admitted **retrieval units**, exclusions and remaining budget. `assembly position` denotes processing order, not a measured retrieval rank.
- `bounded_model_request`: the complete future operation input, not the surrounding preparation record.

**Expected main-input results:**

- `support-addition`, `without graph expansion`: `candidate_fragment_ids` is `[F-1]`; **supplied source evidence** has fragment identifiers `[F-1]`; 145 characters remain.
- `support-addition`, `with graph expansion`: lookup resolves uniquely to `C-RET`; `candidate_fragment_ids` is `[F-1, F-2]`; **supplied source evidence** has fragment identifiers `[F-1, F-2]`; 12 characters remain.
- `budget-exclusion`, `without graph expansion`: `candidate_fragment_ids` is `[F-1, F-3]`; **supplied source evidence** has fragment identifiers `[F-1, F-3]`; 96 characters remain.
- `budget-exclusion`, `with graph expansion`: candidates are `[F-1, F-3, F-2]`; `F-2` fails `context-budget fit` against the remaining 96 characters. **Supplied source evidence** still has fragment identifiers `[F-1, F-3]`; 96 characters remain.

The expanded configurations retain both inspected paths from Student Step 6, including `R-1/R-2` and the intermediate `C-QUERY`. Discovering `F-2` changes **supplied source evidence** only for `support-addition`; the graph supplies no exemption from the budget.

### Student Step 10 — Inspect duplicate-only discovery and unresolved-target fallback

The student prepares the separate policy record. Windows PowerShell and Linux/macOS:

```text
uv run learning-project lab06 prepare-evidence --collection student/lab06-collection --graph reports/lab06/graph-preparation/graph.json --fixture cases/lab06/evidence-policy-probes.json --output reports/lab06/evidence-preparation/policy-probes.json
```

Open `policy-probes.json` and compare the labelled configurations for each probe:

- `duplicate-only`: original candidates already contain `[F-1, F-2]`. Expansion resolves `C-RET` and inspects both paths, but `added_fragment_ids` is empty. Both **bounded model requests** contain the same **supplied source evidence** and have 12 characters remaining.
- `unresolved-target`: original candidates contain only `[F-2]`. Accepted associations for `F-2` identify `C-QUERY` and `C-MODEL`, not `C-RET`. The expanded configuration reports `unresolved`, retains no paths, and continues with `[F-2]`; 117 characters remain. Finding `C-RET` elsewhere in the graph cannot replace the missing association from an original candidate.

Unresolved lookup is not a **refusal** and does not authorize new **entity resolution**. The application still constructs a **bounded model request** from **supplied source evidence** selected from original candidates. Only the later **model-backed prerequisite-explanation operation** can return a **generated prerequisite explanation** or a **refusal** under the declared conditions.

### Student Step 11 — Verify the **bounded model request** boundary and capture `03-evidence-preparation.png`

For every configuration, inspect the exact fields inside `bounded_model_request`:

1. `task instruction`: explain the target's prerequisite connections in the teaching route within the two-edge scope, preserve intermediate concepts and source qualifications, and use only **supplied source evidence**. Insufficient evidence and a conflicting instruction in a selected **retrieval unit** are the two **refusal** conditions.
2. `supplied source evidence`: only admitted complete fragment text with identifiers, character counts and **provenance links**.
3. `output contract`: either one structured **generated prerequisite explanation** with cited claims, or one structured **refusal** naming the blocking condition. JSON field names are laboratory tool syntax, not additional concepts.

The paired **bounded model requests** have identical `task instruction` and `output contract` values. **Graph paths** remain outside the **bounded model requests**. The closed **excluded request fields** also remain outside:

- evaluator-only expected results;
- **relevance judging bases**;
- evaluator-only rubrics or judging instructions;
- unselected **retrieval units**;
- hidden answers.

The student verifies both records on Windows PowerShell or Linux/macOS:

```text
uv run learning-project lab06 verify-evidence --collection student/lab06-collection --graph reports/lab06/graph-preparation/graph.json --evidence reports/lab06/evidence-preparation/evidence-preparation.json
uv run learning-project lab06 verify-evidence --collection student/lab06-collection --graph reports/lab06/graph-preparation/graph.json --fixture cases/lab06/evidence-policy-probes.json --evidence reports/lab06/evidence-preparation/policy-probes.json
```

Each verification must report `Evidence preparation verification passed for 2 teaching inputs and 4 requests; no model output or support judgment verified.` The verifier recomputes the trace and **bounded model requests** against the supplied input and exact accepted graph. Verification does not judge the student's explanation, evidence coverage or generated-output quality.

Stop if a command fails, a verification differs, or an expected candidate/admission result is absent. Preserve inputs and diagnostics; do not edit accepted records, increase the budget or overwrite outputs to manufacture agreement. The commands never overwrite an existing output and never call a model.

Capture `03-evidence-preparation.png`, showing the discovered-but-excluded `F-2`, unresolved-target fallback and successful verification messages. Preserve both JSON records and report notes explaining discovery versus admission and why duplicate-only discovery changes no **bounded model request**. Report initialization and note placement remain part of the later reporting route. The preparation commands produce no model output and make no human support judgment or **bounded configuration decision**.

## Observed prerequisite explanations

The student executes the **model-backed prerequisite-explanation operation** with and without **graph expansion**. The student preserves actual **generated prerequisite explanations** or **refusals**, not the theory's stipulated outputs. This block follows Step 11 and stops before the **human evaluator** judges source support or the **engineering team** makes a **bounded configuration decision**.

The student uses the accepted `student/lab06-collection/`, compiled `reports/lab06/graph-preparation/graph.json`, and verified evidence preparation from Steps 5–11. The course supplies the executable operation and the judging basis from Module 06 Section 5. The commands below run from `training-project/` on Windows, Linux and macOS.

### Student Step 12 — Freeze the shared experiment protocol and bounded model requests

The student checks model access with `agy models`. If authentication is missing, the student runs `agy` interactively and signs in. The documented generator is `gemini-3.8-flash-low`; the student stops if that generator or the existing no-cost allowance is unavailable. The student does not silently substitute a model or enable paid credits. Before execution, the student opens the global language-correction rule file in a text editor, if the file exists:

- Windows PowerShell path: `$HOME\.gemini\GEMINI.md`.
- Linux and macOS path: `~/.gemini/GEMINI.md`.

If the global rule file contains `Apply these rules to every response:`, the student replaces only that clause with `Apply these rules to interactive prose responses only. For requests explicitly requiring machine-readable output, return only the requested format without correcting or restating the prompt.` The student saves the global rule file without changing other preferences. If the global rule file is absent or already exempts machine-readable requests, no file change is required. If another rule conflicts with the JSON output contract, the student stops and asks the instructor to resolve the conflict. An empty working directory does not disable global AGY rules.

The student prepares the **shared experiment protocol** before inspecting the current run's outputs:

```text
uv run learning-project lab06 prepare-generation --collection student/lab06-collection --graph reports/lab06/graph-preparation/graph.json --model gemini-3.8-flash-low --output reports/lab06/generation/protocol.json
```

The complete **evaluation cases** name a version, development membership, risk group, public-source provenance, collection scope, original candidates, evaluator-only **reference** and reviewer metadata:

- `EC-06-1-v1` uses original candidate `F-1`; **graph expansion** adds `F-2` before admission.
- `EC-06-2-v1` uses original candidates `F-1,F-2`; duplicate-only discovery leaves the paired **bounded model requests** equal. This case is not Step 9's budget-exclusion input.

Both cases ask for the two-edge prerequisite explanation for **Embedding-based retrieval**. The **reference** requires the connections from **Embedding-based retrieval** to **Query embedding** and from **Query embedding** to **Embedding model**, with the teaching-route qualification. The **reference** and judging instructions remain outside generation.

The **shared experiment protocol** fixes the following items:

- One AGY model, provider-default sampling, shared prompt prefix and JSON outcome schema for both configurations. AGY receives no sampling-seed guarantee.
- The unchanged Step 11 **task instruction**, **output contract**, **retrieval-unit admission criteria** and 250-character **context budget**. Generation receives only the three **bounded model request** fields, never graph paths, the **reference** or **acceptance conditions**.
- One invocation per case and configuration, without automatic retries or selection of favorable attempts. AGY may use several internal turns; every returned envelope remains available.
- Course-selected **acceptance conditions**: minimum **rubric pass rate** 1.0; blocking unsupported claims or an explanation despite a conflicting instruction; maximum question-time duration 360 seconds; maximum human-review effort 10 minutes per output; maximum 200,000 reported total tokens per configuration over both cases. Missing operational evidence permits no decision. These teaching limits are not measured deployment requirements.
- Existing no-cost allowance only, with paid-credit fallback disabled. If both configurations qualify, the higher **rubric pass rate** wins; a tie retains the configuration without **graph expansion**. Any later decision is limited to these exposed **development cases**.

Expected result: `Prepared two development cases and four bounded model requests; no model call.` The student checks the model, case identities, paired evidence and limits in `protocol.json` before continuing. An existing output, changed accepted graph or unavailable input stops preparation; the student preserves the existing artifacts rather than overwriting them.

### Student Step 13 — Preserve actual operation outcomes under both configurations

The student executes the following four positions in order. The same commands apply on Windows, Linux and macOS:

```text
uv run learning-project lab06 run-generation --collection student/lab06-collection --graph reports/lab06/graph-preparation/graph.json --protocol reports/lab06/generation/protocol.json --case EC-06-1-v1 --configuration "without graph expansion" --output-dir reports/lab06/generation/runs/EC-06-1-v1/without-graph-expansion
uv run learning-project lab06 run-generation --collection student/lab06-collection --graph reports/lab06/graph-preparation/graph.json --protocol reports/lab06/generation/protocol.json --case EC-06-1-v1 --configuration "with graph expansion" --output-dir reports/lab06/generation/runs/EC-06-1-v1/with-graph-expansion
uv run learning-project lab06 run-generation --collection student/lab06-collection --graph reports/lab06/graph-preparation/graph.json --protocol reports/lab06/generation/protocol.json --case EC-06-2-v1 --configuration "without graph expansion" --output-dir reports/lab06/generation/runs/EC-06-2-v1/without-graph-expansion
uv run learning-project lab06 run-generation --collection student/lab06-collection --graph reports/lab06/graph-preparation/graph.json --protocol reports/lab06/generation/protocol.json --case EC-06-2-v1 --configuration "with graph expansion" --output-dir reports/lab06/generation/runs/EC-06-2-v1/with-graph-expansion
```

For each position, the command creates the following artifacts without changing accepted records, the graph or the frozen protocol:

- `attempt.json` reserves the position before a provider call and binds the case, configuration, generator and request.
- `provider-response.json` preserves complete stdout, stderr and process status, including reported usage and denied actions when present.
- `outcome.json` preserves the extracted **generated prerequisite explanation** or **refusal**, including a failing attempted explanation. Extraction uses the envelope's explicit `structured_output`; without that field, extraction requires exactly one nonempty JSON object and permits only empty JSON placeholders alongside that object. Prose, malformed JSON or multiple nonempty objects stop extraction; the command does not choose the best answer.
- `run-metadata.json` records the outcome status and generation-process duration separately from question-time duration. Question-time measurement includes accepted-graph validation and replay of paired evidence preparation through persisted outcome; graph construction and human judging are excluded. The shared validation overhead is included in both configurations. Token evidence comes from the raw AGY envelope, not character counts.

Expected success message for each completed position: `Preserved provider response and extracted outcome; no semantic judgment.` The four positions may produce attempted explanations or refusals; neither outcome type is guaranteed. The student preserves the student's own responses without substituting a different capture.

If a position fails, the student stops before the next position, keeps the complete capture and failure metadata, and leaves unstarted positions unstarted. The student does not delete the reserved attempt to retry. The student does not repair the parser, import a replacement, or repeat the model call. The student asks the instructor to inspect the preserved capture.

Any instructor-assisted offline recovery remains separately recorded with the original capture and failure evidence; import processing time is not model latency. A **refusal** is a model outcome, not the application's replacement for a failed provider call.

### Student Step 14 — Verify outcome provenance and claim-citation identifiers

The student runs the structural verification:

```text
uv run learning-project lab06 verify-generation --collection student/lab06-collection --graph reports/lab06/graph-preparation/graph.json --protocol reports/lab06/generation/protocol.json --runs-dir reports/lab06/generation/runs
```

The student checks the following labelled results:

- `observed_outputs: 4` means all four captures match their extracted objects and frozen request bindings.
- `structural_issues: []` means the checked outcome fields and **claim citation** identifiers have the required structure. Resolvable identifiers do not establish source support, completeness or the correctness of a **refusal**.
- `semantic_judgment: not performed` and `configuration_decision: not authorized` preserve the boundary before human judging.

A missing or mismatched capture stops verification. A nonempty structural-issue list remains attached to the actual output; an identifiable attempted explanation proceeds to the **Prerequisite explanation check** as a potentially failing output, never as a substituted **refusal**. An unidentifiable output is an execution failure and stops response judging. The student records `04-observed-outcomes.png`, showing the four position results and verification output, and notes any interruption or offline recovery for the later report route. Report assembly belongs to the completion steps; no quality rate or configuration decision is claimed here.

## Independent judgments and the bounded configuration decision

The student separately acts as **human evaluator** and **engineering team**. The **human evaluator** judges the admitted **supplied source evidence** and actual operation outcomes. The **engineering team** uses configuration-local **rubric pass rates** and the frozen **acceptance conditions** to record a **bounded configuration decision**. A deterministic check does not judge source support or authorize deployment.

This block follows Step 14. The student uses the unchanged collection, compiled graph, `protocol.json` and four position directories from Steps 12–14. Commands run from `training-project/` on Windows, Linux and macOS. Missing captures, changed bindings or an unidentifiable outcome stop judging; the student preserves the evidence and contacts the instructor.

### Student Step 15 — Record independent evidence and response judgments

The student prepares the judging file:

```text
uv run learning-project lab06 prepare-judgments --collection student/lab06-collection --graph reports/lab06/graph-preparation/graph.json --protocol reports/lab06/generation/protocol.json --runs-dir reports/lab06/generation/runs --output reports/lab06/judgments.json
```

Expected result: `Prepared four bound positions; human judgments remain blank.` The file contains the actual request, evaluator-only **reference**, outcome and structural issues for each position. The student checks these four labelled positions in order:

- `EC-06-1-v1` — `without graph expansion`.
- `EC-06-1-v1` — `with graph expansion`.
- `EC-06-2-v1` — `without graph expansion`.
- `EC-06-2-v1` — `with graph expansion`.

The **human evaluator** opens `judgments.json` in a text editor and sets `human_evaluator` to a chosen evaluator label. For each position, the **human evaluator** times the complete inspection of the request, **reference**, output and rubric, then replaces the following `null` fields with actual judgments:

- `supported_connections`: two Boolean values, in the order of `reference.required_connections`. Each value states whether the admitted source text supports that required connection, including the intermediate concept and teaching-route qualification. Fragment presence alone is not support.
- `evidence_reason`: a nonempty reason identifying the supporting admitted text or the missing connection.
- `conflicting_instruction_present`: a Boolean judgment of whether a selected retrieval unit contains an instruction conflicting with the **task instruction**. An unresolved **entry-node lookup** is not a third **refusal** condition.
- `response_checks`: the outcome-specific checks described below.
- `judgment`: `"pass"` or `"fail"` under the applicable rubric check.
- `response_reason`: a nonempty explanation tied to the actual output and cited admitted text.
- `review_minutes`: measured positive minutes for that position, including evidence and response inspection, not model waiting time.

For a **generated prerequisite explanation**, the **human evaluator** applies the **Prerequisite explanation check** through these Boolean fields:

- `required_concepts_and_connections`: the explanation expresses all required concepts and connections within the two-edge scope, preserving the intermediate concept rather than inventing a direct accepted edge.
- `teaching_route_qualification`: the explanation preserves the source qualification.
- `supporting_claim_citations`: every factual claim has a citation whose admitted text supports the claim, not merely a resolvable identifier.
- `unsupported_claim`: at least one factual claim lacks support in the admitted text.

A passing explanation requires all required connections to be supported in the admitted evidence, no conflicting instruction, `required_concepts_and_connections`, `teaching_route_qualification` and `supporting_claim_citations` true, and `unsupported_claim` false. An incomplete attempted explanation remains a failing explanation, not a **refusal**. An identifiable explanation with missing fields or citations also fails; the **human evaluator** does not repair or replace the actual output.

For a **refusal**, the file instead contains `response_checks.blocking_condition_holds`. The **human evaluator** sets `response_checks.blocking_condition_holds` to Boolean `true` when the model's stated blocking condition holds in the actual request, and to `false` otherwise. The **human evaluator** applies the **Refusal check** to the model's stated condition: insufficient admitted evidence or a conflicting instruction. A **refusal** claiming insufficiency fails when the admitted text supports both required connections and no conflicting instruction blocks the task. The output type selects the check; the **human evaluator** cannot switch checks to obtain a pass.

The **human evaluator** saves only the judgment fields listed above and `human_evaluator`. The student leaves the request, **reference**, actual outcome, position order and bindings unchanged. Separate evidence and response reasons preserve possible disagreement between evidence coverage and output quality. Blank fields remain outstanding, never implicit passes; a contradicting pass/fail record stops assessment.

### Student Step 16 — Inspect configuration-local rates and all acceptance conditions

The student records the comparison assessment:

```text
uv run learning-project lab06 assess-comparison --collection student/lab06-collection --graph reports/lab06/graph-preparation/graph.json --protocol reports/lab06/generation/protocol.json --runs-dir reports/lab06/generation/runs --judgments reports/lab06/judgments.json --output reports/lab06/comparison.json
```

The student inspects these labelled fields in `comparison.json`:

- `positions`: preserves evidence coverage and response judgment separately, with recorded human effort, question-time duration and reported total tokens.
- `configurations`: reports explanation passes, **refusal** passes, judged outputs and outstanding judgments separately for each configuration. The **rubric pass rate** numerator is explanation passes plus **refusal** passes; the denominator includes every judged output of that configuration, including failures. Zero judged outputs produces `null`, not a zero or perfect rate.
- `configurations[configuration].acceptance_conditions`: checks the unchanged minimum **rubric pass rate** 1.0, blocking failures, maximum question-time duration 360 seconds, maximum human-review effort 10 minutes per outcome and maximum 200,000 reported total tokens per configuration over both cases. Token evidence comes from the preserved AGY envelopes, not fragment characters.
- `complete` and `missing_evidence`: identify missing judgments, effort, comparable timing or token usage. A partial rate does not make an incomplete comparison eligible for a decision.
- `permitted_decision`: identifies the branch permitted by complete evidence and the frozen preference; `configuration_decision: not recorded` means the **engineering team** has not recorded a decision.

An unsupported claim or an explanation despite a conflicting instruction blocks the producing configuration independently of other outputs. Condition results use `true` for satisfied, `false` for a demonstrated failure and `null` for unknown. A known limit exceedance fails its condition; unknown evidence does not count as a satisfied limit. The frozen conditions permit these mutually exclusive branches:

- Both configurations qualify: select the higher **rubric pass rate**; a tie permits `retain without graph expansion`.
- Only `without graph expansion` qualifies: `retain without graph expansion`.
- Only `with graph expansion` qualifies: `adopt with graph expansion`.
- Neither configuration qualifies: `accept neither`.

If `complete` is false, the student preserves `comparison.json` and records no adoption, retention or accept-neither decision. Offline recovery does not supply a measured complete live question-time path. The original failed attempt's process duration and offline import duration cannot replace that measurement. Incomplete comparable timing leaves the comparison incomplete; the student does not invent timings or treat an incomplete path as a prescribed decision.

### Student Step 17 — Record the engineering team's bounded decision

Only with `complete: true`, the student acting as **engineering team** creates `reports/lab06/decision-input.json` in a text editor, replacing all five `null` values with nonempty strings:

```json
{
  "engineering_team": null,
  "decision": null,
  "rationale": null,
  "teaching_prediction_comparison": null,
  "graph_preparation_trade_off": null
}
```

The **engineering team** records:

- `engineering_team`: a chosen engineering-team label, distinct in role from the evaluator label even when one student holds both responsibilities.
- `decision`: the exact `permitted_decision` value: `retain without graph expansion`, `adopt with graph expansion` or `accept neither`.
- `rationale`: the observed quality and operational evidence supporting the permitted branch, including any blocking failure.
- `teaching_prediction_comparison`: how the student's actual judgments agree with or differ from the theory's stipulated comparison; the student does not substitute the theory's outputs or rates.
- `graph_preparation_trade_off`: one observed discovery/coverage or operational trade-off, accounting separately for graph construction, human review and maintenance burden. The student does not invent preparation timings or claim deployment benefit from two exposed **development cases**.

The student records the explicit decision:

```text
uv run learning-project lab06 record-decision --collection student/lab06-collection --graph reports/lab06/graph-preparation/graph.json --protocol reports/lab06/generation/protocol.json --runs-dir reports/lab06/generation/runs --judgments reports/lab06/judgments.json --assessment reports/lab06/comparison.json --decision-input reports/lab06/decision-input.json --output reports/lab06/decision.json
```

Expected result: `Recorded engineering team decision for development cases; no accepted-state write.` The command recomputes the assessment and rejects a stale assessment, incomplete evidence or a decision contradicting the frozen conditions. Existing outputs stop creation without overwriting. The student preserves failing judgments and does not change thresholds, repeat generation or select favorable attempts to obtain a different decision.

The student records `05-comparison-decision.png`, showing the two labelled **rubric pass rates**, condition results, completeness and the recorded bounded decision, or the missing-evidence/no-decision result when the comparison is incomplete. The completion steps assemble the report and transfer exercise; this checkpoint does not claim whole-laboratory completion, held-out generalization or deployment authorization.

## Transfer, report, final verification, and submission

The student completes one bounded transfer outside the teaching collection, finishes the source report, binds the complete or honest-partial evidence to one exact final commit, and prepares the standalone submission copy for Microsoft Teams. The report route starts at Student Step 1: the student initializes `reports/lab06/REPORT.md` from the supplied template and creates the screenshot directory before the first graph-preparation checkpoint.

The course supplies `fixtures/lab06/REPORT.md`. The student owns:

- identity fields (name, student id, fork URL, personal branch `lab06/<student-id>`, completion state);
- checkpoint prose under `## Хід виконання`;
- conclusions under `## Висновки`;
- named screenshots under `reports/lab06/screenshots/`;
- machine-readable evidence already produced by the graph, query, evidence-preparation, generation, and judgment path, plus `verification-report.json` after final verification.

Deterministic `validate-report` and `verify` check structure, identity, checkpoint links, evidence presence or partial scope, and commit binding. They do not judge source support, explanation quality, or goal attainment.

### Student Step 18 — Bounded transfer of one connection

The student applies the already taught representation and review boundary to one public or synthetic connection from another study area. No new model cohort, no second configuration comparison, and no write into `student/lab06-collection` are authorized.

In the report checkpoint **Перенесення одного зв’язку**, the student records:

1. the other study area and one public or synthetic fragment with source id, version, location, and exact text;
2. two concept identifiers, primary labels, type `Concept`, and mention spans in that fragment;
3. one proposed `requires` edge with dependent → prerequisite direction, qualification, and support-fragment reference;
4. separate structural validation versus the student's own source-support judgment;
5. decision `accept`, `reject`, or `blocked` with a source-based reason.

The teaching accepted graph and disposable collection remain unchanged. Capture `06-transfer-review.png` showing the written transfer record (editor or terminal view) with account identity and system date visible.

**Expected result:** the transfer checkpoint explains one reviewed connection without claiming collection mutation or a new generation comparison.

### Student Step 19 — Complete the source report

Replace or remove every bracketed fixture prompt and the opening instruction paragraph. Keep the four mandatory headings in order: `Ідентифікація`, `Мета роботи`, `Хід виконання`, `Висновки`.

For each reached checkpoint under `## Хід виконання`, write formal Ukrainian technical prose that separates:

- the action performed;
- the observed result;
- the reason continuation or stop was justified;
- consistency with the named machine-readable evidence.

Do not use first-person narration. Do not insert internal course-development labels. For `complete`, keep all seven screenshot links. For `honest-partial`, remove only links for checkpoints never started, keep every reached checkpoint link, keep `07-final-verification.png`, and fill **Межа зупинки** with the last action, exact command or manual check, observed error or missing evidence, and missing results. Do not invent missing outputs, rates, timings, or screenshots.

Set completion state to `complete` only when the required graph-through-decision evidence and the transfer checkpoint are present. Otherwise use `honest-partial`.

Windows PowerShell and Linux/macOS:

```text
uv run learning-project lab06 validate-report --report-dir reports/lab06
```

**Expected result:** validation status `passed`. On failure, repair the named structural defect; do not edit committed generation or judgment bytes to manufacture agreement.

### Student Step 20 — Commit and verify the exact branch head

From `training-project/` after validation passes:

Windows PowerShell:

```powershell
git add reports/lab06 student/lab06-collection
git commit -m "Laboratory 06 report"
git rev-parse HEAD
uv run learning-project lab06 verify --report-dir reports/lab06 --collection student/lab06-collection --final-commit <full-commit-hash>
```

Linux and macOS:

```bash
git add reports/lab06 student/lab06-collection
git commit -m "Laboratory 06 report"
git rev-parse HEAD
uv run learning-project lab06 verify --report-dir reports/lab06 --collection student/lab06-collection --final-commit <full-commit-hash>
```

Use the exact full 40-character hash of the current branch head. Verification checks report structure, personal-branch match, commit membership of report evidence and `student/lab06-collection/accepted.json` when present, and—only for `complete`—replay of existing deterministic domain checks against recorded human inputs. It does not rejudge support or invent a configuration decision. Partial verification may pass preservation checks with `domain_completion_claimed` false.

After success, capture `07-final-verification.png` showing the pass outcome, account identity, and system date. Only `reports/lab06/verification-report.json`, `reports/lab06/screenshots/07-final-verification.png`, and later `reports/lab06/submission/REPORT.md` may appear after the final commit.

**Expected result:** `verification-report.json` records outcome `passed` for the exact HEAD. Existing verification output is never overwritten.

### Student Step 21 — Prepare the standalone submission report

Windows PowerShell and Linux/macOS:

```text
uv run learning-project prepare-report reports/lab06/REPORT.md
```

**Expected result:** `reports/lab06/submission/REPORT.md` embeds the checkpoint images present in the source report. The source report keeps relative links and is unchanged. The generated Teams file is ignored by Git and is not committed.

#### Stopping paths

If a command fails before the report route, preserve the error and existing files, set completion state `honest-partial`, complete the report for reached work only, validate, commit, verify, and package. Do not delete failed captures, overwrite create-only outputs, or substitute import or failure duration for a missing successful complete-path timing. Incomplete comparison evidence still permits no configuration decision.

## Final verification

The work is ready for demonstration only when all of the following success conditions hold:

1. The graph, query, evidence-preparation, generation, and evaluation verifiers that were reached pass at their declared boundaries, or the report honestly records the stopping boundary for any unreached path.
2. `reports/lab06/REPORT.md` preserves every mandatory heading, contains the required relative screenshot links for reached checkpoints plus final verification, contains no bracketed instructional prompt, and passes `lab06 validate-report`.
3. The required screenshots exist with the required visible result, account identity, and system date.
4. The exact current branch head passes `lab06 verify`, and `reports/lab06/verification-report.json` names that full commit hash.
5. No committed evidence is edited after final verification except the permitted post-commit verification screenshot, verification report and generated submission copy.
6. `learning-project prepare-report reports/lab06/REPORT.md` produces `reports/lab06/submission/REPORT.md` with the reached checkpoint images embedded.

A failed check is a stopping condition, not permission to delete or overwrite recorded evidence. Preserve the failing message and follow the stopping path named in the owning student step.

## Submission artifacts

See [LABORATORY_STANDING_RULES.md](../../LABORATORY_STANDING_RULES.md) for the standing submission rules.

Submit exactly one Microsoft Teams attachment:

- `reports/lab06/submission/REPORT.md` — the standalone narrative report containing the reached embedded checkpoint images.

The machine-readable evidence, `reports/lab06/verification-report.json`, the source screenshot files, and the source `reports/lab06/REPORT.md` remain in the verified Git commit and are not additional Microsoft Teams attachments. Do not write a separate Microsoft Teams cover message and do not fill the assignment text field.

## Control questions

1. Why must **structural validation** remain separate from human source-support judgment when a conforming reversed prerequisite claim is present?
2. Why does a two-edge **graph path** through an intermediate concept not authorize a new direct accepted edge between the path endpoints?
3. Why may **graph expansion** discover a fragment that still fails admission into **supplied source evidence**?
4. Why must **graph paths**, the evaluator-only **reference** and **acceptance conditions** remain outside every **bounded model request**?
5. Why does a resolvable **claim citation** fail to establish that the admitted text supports the claim?
6. Why are **rubric pass rates** calculated separately for each evidence-preparation configuration, and when must the **engineering team** record no decision?
7. Which decision does the **bounded configuration decision** make, and which deployment, collection-write and held-out-evidence claims remain outside its authority?
8. What must the transfer checkpoint demonstrate without mutating `student/lab06-collection`?

## Optional extensions

No optional extension is assigned. Do not change the frozen protocol, add evaluation cases, substitute model identifiers, rerun a case–configuration pair over existing evidence, or widen the **bounded configuration decision** unless the instructor supplies a separately reviewed extension contract.
