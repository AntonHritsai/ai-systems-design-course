# Module 03: Evaluation and Experiment Design — Laboratory

> **Status:** Ready for Students — English laboratory and Ukrainian translation approved by the instructor on 2026-10-04

## Goal

Obtain the evidence that the engineering team needs to decide whether candidate configuration Variant B should replace experiment baseline Variant A for the evaluated use of the model-backed concept-proposal operation.

## Tasks

- as the human evaluator, assign one rubric category to each of four authored fixtures and compare the judgments with the course-provided reviewed labels;
- as the human evaluator, use two development cases provided and controlled by the course to inspect Variant A's candidate outputs against the supplied sources and the evaluation rubric; then, as the engineering team, define the intended factor as the exact instruction-property difference between Variant A and Variant B;
- as the engineering team, freeze the shared experiment protocol before the Laboratory 03 workflow reveals held-out cases to the student;
- as the engineering team, run Variant A and Variant B on the same held-out cases and preserve each scheduled attempt record with either its returned response or its recorded failure outcome; as the human evaluator, assign each structurally valid returned response one rubric category;
- as the engineering team, report the five successive counts for each configuration, record one bounded configuration decision, and preserve one reviewed regression case.

## Expected result

The `reports/lab03/` and `student/lab03/` evidence package contains:

- four authored-fixture judgments;
- four development attempts;
- one declared intended factor;
- one frozen shared experiment protocol;
- one related-scenario group of held-out cases provided and controlled by the course;
- sixteen held-out scheduled attempts;
- one source-grounded absolute assessment for each structurally valid returned response;
- five successive counts for each configuration;
- one bounded configuration decision;
- one reviewed regression case;
- a passing `lab03 verify` result bound to the final student commit.

Variant B is not required to have more accepted-by-rubric responses than Variant A. The held-out comparison record may justify `recommend-b`, `retain-a`, `reject-both`, or `seek-more-evidence`. Laboratory 03 does not modify the accepted `Structured Output` concept and does not authorize deployment or an accepted-knowledge write.

During Laboratory 03, the student acts in two distinct roles. As the human evaluator, the student assigns rubric categories to candidate outputs. As the engineering team, the student defines the shared experiment protocol and records the bounded configuration decision. The knowledge owner and authorized human reviewer do not act in the response-level Laboratory 03 workflow, and neither laboratory role may authorize an accepted-knowledge write.

The rubric judgments and successive counts describe response-level evidence about the model-backed concept-proposal operation. Laboratory 03 does not assess completion of the end-to-end knowledge workflow.

## Expected competencies

After completing the laboratory, the student can:

- distinguish development, held-out, and regression cases;
- apply the `S`, `I`, `U`, `Q`, `R`, and `X` rubric to each structurally valid returned candidate output against the case's supplied source evidence and evaluator-only expected behavior, using `X` when the proposed text or required evaluation evidence does not permit semantic assessment;
- compare an experiment baseline and a candidate configuration under one shared experiment protocol;
- preserve comparability by changing one intended factor and freezing the cases, supplied sources, output contract, model and access route, evaluation rubric, repeat policy of two scheduled attempts per case and configuration, and retry policy of zero retries;
- interpret attempted, returned, structurally valid, assessable, and accepted-by-rubric counts;
- interpret critical failures, slice results, differences between scheduled attempts, latency measured on the declared timing boundary, and unknown usage or cost values as side evidence rather than additional successive denominators;
- as the engineering team, make a bounded configuration decision without treating human-evaluator judgments as authority to deploy a configuration or authorize an accepted-knowledge write;
- preserve one confirmed failure as a reviewed regression case.

## Prerequisites

Complete Laboratory 03 independently before the scheduled session. The session is reserved for demonstration and defense. The standing rules in [`LABORATORY_STANDING_RULES.md`](../../LABORATORY_STANDING_RULES.md) apply.

The required starting conditions are:

- Module 03 theory, especially §§1, 2, 4, 5, 6, and 7, has been studied; §3 is required for the optional AI-judge extension;
- Laboratories 01 and 02 are complete and pushed to the student's fork;
- the external vault and project clone still contain the Laboratory 02 accepted-state artifacts that `lab02 verify` checks;
- Git and `uv` are installed, and an OpenRouter route is available.

The documented live route is `openrouter/free`. Free availability can change. No purchase is required. The student must run each scheduled provider call at most once so that the CLI records the scheduled attempt with either a returned response or a failure outcome.

Route unavailability is handled by these branches:

- if neither Variant A development attempt returns a response, follow the Step 3 `honest-partial` branch;
- if at least one Variant A development attempt returns a response but both Variant B development attempts have failed outcomes whose `error.json` records identify route-wide unavailability, preserve all four terminal development attempts, skip Steps 5–9, record `honest-partial` completion in Step 10 with `stopped_at_step: "Step 4"`, and continue with Step 11 only;
- route unavailability after the held-out comparison begins follows the Step 6 recovery branch.

An offline authored fixture is not current model-behavior evidence for Variant A or Variant B.

Keep provider credentials outside commands, files, screenshots, commits, and submissions. The student supplies the external-vault path only to the Laboratory 02 admission check in Step 1. Laboratory 03 must not create or modify a file in the external vault.

## Starting state

Create the branch from the completed Laboratory 02 branch:

```powershell
git switch lab02/<student-id>
git switch -c lab03/<student-id>
cd .\training-project
$vault = "C:\absolute\path\to\ai-systems-learning-vault"
```

Linux and macOS use the same Git commands, `cd training-project`, and `vault="/absolute/path/to/ai-systems-learning-vault"`.

The student writes only under `training-project/reports/` and `training-project/student/`. The course provides and controls `cases/lab03/`, `instructions/lab03/`, `schemas/`, `platform/`, and `tests/public/`.

The student-owned inputs are `variant-b.txt`, `change-declaration.yaml`, `protocol-draft.yaml`, `regression.yaml`, and `completion-detail.yaml`. Generated evidence is stored under `reports/lab03/`. Attempt and comparison records are write-once. Do not delete a scheduled attempt's returned response or recorded failure outcome and reuse that scheduled attempt's `--position-id`. Do not delete a recorded assessment and reuse that assessment's `--blind-id`.

## Steps

### Step 1: Verify admission and initialize the report

Copy `reports/lab02/` to a disposable directory and run `lab02 verify` on the disposable copy so that the committed Laboratory 02 evidence remains unchanged.

```powershell
$admission = Join-Path ([System.IO.Path]::GetTempPath()) "lab02-admission-<student-id>"
Copy-Item .\reports\lab02 $admission -Recurse
uv run learning-project lab02 verify --vault "$vault" --report-dir $admission
Remove-Item $admission -Recurse -Force
```

Linux and macOS use:

```bash
admission="$(mktemp -d)"
cp -R reports/lab02/. "$admission/"
uv run learning-project lab02 verify --vault "$vault" --report-dir "$admission"
rm -rf "$admission"
```

`lab02 verify` must print `Laboratory 02 verification passed.` If `lab02 verify` fails, stop before creating Laboratory 03 evidence, complete Laboratory 02 under the Laboratory 02 instructions, and then restart Laboratory 03 from Starting state.

After admission passes, fetch `upstream/main`, merge the fetched `upstream/main` publication state into the Laboratory 03 branch, and initialize the report:

```powershell
cd ..
git fetch upstream
git merge upstream/main
cd .\training-project
New-Item -ItemType Directory -Force .\reports\lab03\screenshots | Out-Null
if (-not (Test-Path .\reports\lab03\REPORT.md)) {
  Copy-Item .\fixtures\lab03\REPORT.md .\reports\lab03\REPORT.md
}
New-Item -ItemType Directory -Force .\student\lab03 | Out-Null
```

Linux and macOS use `mkdir -p reports/lab03/screenshots student/lab03` and `test -f reports/lab03/REPORT.md || cp fixtures/lab03/REPORT.md reports/lab03/REPORT.md`.

**Expected result:** admission prints the required pass line; `reports/lab03/REPORT.md` and `student/lab03/` exist; the student has not added a Laboratory 03 file under the external-vault path.

### Step 2: Anchor rubric use with authored fixtures

The file `cases/lab03/calibration/calibration-a/packet.json`, which the course provides and controls, contains four authored fixtures that anchor the evaluation rubric. The authored fixtures prepare the student to act as the human evaluator; the authored fixtures are not evidence of `openrouter/free` model performance.

```powershell
uv run learning-project lab03 calibrate --report-dir reports/lab03 `
  --packet calibration-a --by "<student-id>"
```

After `calibrate` creates the student-label file, open only `tasks` and `authored_outputs` in `cases/lab03/calibration/calibration-a/packet.json`; do not open the reviewed labels or other keys. Apply the task-specific expected behaviors established in Module 03 §2.3: the source-baseline task must preserve the relation between the source baseline and the material used to review a proposal, while the retention-duration task must state that the supplied source does not specify a duration. In the generated `reports/lab03/calibration/calibration-a/student-labels.yaml`, assign each authored fixture one category from `S`, `I`, `U`, `Q`, `R`, or `X` and write a rationale that cites the fixture's task, supplied source, task-specific expected behavior, and evaluation-rubric rule.

```powershell
uv run learning-project lab03 calibrate-submit --report-dir reports/lab03 `
  --packet calibration-a --by "<student-id>"
```

After `calibrate-submit`, do not edit the stored student labels to match the course-provided reviewed labels. In `REPORT.md`, explain each pair for which the student's category differs from the reviewed label. If the student opened the reviewed labels in `calibration-a` before submitting the student labels, preserve that packet's files and repeat Step 2 once with `--packet calibration-b`. If the reviewed labels in both packets were opened before submission, stop the comparison, record `honest-partial` completion in Step 10 with `stopped_at_step: "Step 2"`, and continue with Step 11 only.

**Expected result:** one packet directory contains four immutable student judgments and the comparison of the four student judgments with the course-provided reviewed labels. Capture the `calibrate-submit` result as `reports/lab03/screenshots/01-calibration.png`.

### Step 3: Run Variant A on two development cases

The course provides and controls two development cases whose tasks, supplied sources, and expected behaviors the student may inspect before creating Variant B:

- `dev-source-baseline-definition` — the source evidence is sufficient to state the source-baseline relation;
- `dev-approval-authority-absent` — the source does not name an approval authority, so a confident claim about that authority is unsupported.

Enter the OpenRouter credential through the process environment. Windows PowerShell:

```powershell
$secure = Read-Host "OpenRouter API key" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
$env:OPENROUTER_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
Remove-Variable secure, bstr

uv run learning-project lab03 dev-run --report-dir reports/lab03 --position-id pos-dev-source-baseline-definition-a-1 --adapter openrouter --model-id openrouter/free --by "<student-id>"
uv run learning-project lab03 dev-run --report-dir reports/lab03 --position-id pos-dev-approval-authority-absent-a-1 --adapter openrouter --model-id openrouter/free --by "<student-id>"
```

Linux and macOS use `read -s OPENROUTER_API_KEY`, `export OPENROUTER_API_KEY`, the same `uv run` commands, and `unset OPENROUTER_API_KEY` after live execution.

For each returned Variant A response, run:

```powershell
uv run learning-project lab03 dev-structural-check --report-dir reports/lab03 `
  --position-id <returned-position-id>
```

Every scheduled attempt reaches one terminal outcome. A `returned` outcome means that the scheduled attempt produced a model response; the produced model response enters the returned-response count even when the response structure or response meaning is defective. A `failed` outcome means that the scheduled attempt produced no model response; the failed scheduled attempt enters the attempted-operation count but not the returned-response count. Neither terminal scheduled attempt may be replaced. If the process ended after a scheduled attempt's `request.json` was written but before a terminal outcome was recorded, run the following command for the interrupted scheduled attempt rather than dispatching the interrupted `--position-id` again:

```powershell
uv run learning-project lab03 dev-record-interrupted --report-dir reports/lab03 `
  --position-id <interrupted-position-id> `
  --reason "process ended before terminal evidence was recorded" `
  --by "<student-id>"
```

If one Variant A development attempt fails, preserve that attempt's `error.json` and continue with the other development evidence. If both Variant A development attempts fail, preserve both `error.json` records, skip Steps 4–9, record `honest-partial` completion in Step 10 with `stopped_at_step: "Step 3"`, and continue with Step 11 only.

**Expected result:** both Variant A development attempts are terminal, and every returned response has a `dev-structural-check` result.

### Step 4: Define and test one intended factor between Variant A and Variant B

As the engineering team, use the two development cases' tasks, supplied sources, evaluator-only expected behaviors, the Variant A outputs from Step 3, and the evaluation rubric to identify one instruction property for the comparison to vary. Define the intended factor as the exact Variant A value of the selected instruction property versus the exact Variant B value of the selected instruction property. Create `student/lab03/variant-b.txt` from `instructions/lab03/variant-a.txt` by changing exactly the selected instruction property. Preserve the concept-proposal task and the two-field output contract containing `case_id` and `proposed_text`.

Create `student/lab03/change-declaration.yaml`:

```yaml
changed_property: <one instruction property>
mechanism: <how the change could affect source-grounded behavior>
declared_factors:
  - <the same property named in changed_property>
```

As the engineering team, record Variant B and run the candidate configuration on the same two development cases:

```powershell
uv run learning-project lab03 record-variant-b --report-dir reports/lab03 `
  --text student/lab03/variant-b.txt `
  --change student/lab03/change-declaration.yaml

uv run learning-project lab03 dev-run --report-dir reports/lab03 --position-id pos-dev-source-baseline-definition-b-1 --adapter openrouter --model-id openrouter/free --by "<student-id>"
uv run learning-project lab03 dev-run --report-dir reports/lab03 --position-id pos-dev-approval-authority-absent-b-1 --adapter openrouter --model-id openrouter/free --by "<student-id>"
```

Run `dev-structural-check` for every returned Variant B response. Do not edit `variant-b.txt` or `change-declaration.yaml` after inspecting the Variant B outputs or the Variant B structural results within the current comparison. If results from a later held-out comparison influence another revision of Variant B, any new final comparison of the revised Variant B configuration requires genuinely unseen held-out cases.

**Expected result:** the development attempt list contains two Variant A attempts followed by two Variant B attempts; all four attempts are terminal; `change-declaration.yaml` names the selected instruction property whose Variant A value and Variant B value form one intended factor. Capture the development attempt list as `reports/lab03/screenshots/02-development.png`.

### Step 5: Freeze the shared experiment protocol

As the engineering team, before opening held-out material, create `student/lab03/protocol-draft.yaml`. The `engineering_decision` field states the decision question that the comparison must inform; the `engineering_decision` field does not contain the post-comparison outcome recorded in Step 8. The `semantic_acceptance` and `operational_acceptance` fields state the frozen acceptance conditions. The `blocking_failures` field states which critical failure violates a blocking condition. The `tradeoff_rule` field states when the measured evidence would justify replacing acceptable Variant A with Variant B.

```yaml
engineering_decision: <whether B should replace A for the evaluated use>
hypothesis: <predicted effect of the intended factor on source support and meaning coverage>
semantic_acceptance: <meaning-coverage numerator, denominator, and threshold for each configuration>
blocking_failures: <critical failure U that violates a blocking condition for a configuration>
operational_acceptance: <latency boundary measured from attempt start to returned response, plus the rule for unknown latency or usage measurements>
tradeoff_rule: <when B may replace acceptable A; do not claim dominance over an unknown relevant dimension>
decision_rule:
  recommend-b: <B satisfies every blocking condition and justifies the change>
  retain-a: <A remains acceptable and B does not justify a change>
  reject-both: <both configurations violate a blocking condition>
  seek-more-evidence: <relevant evidence or uncertainty remains unresolved>
attempt_budget: 16
timing_boundary: <the same measured interval for both configurations>
route:
  adapter: openrouter
  model_id: openrouter/free
```

The mandatory comparison uses two attempts per case for each configuration and permits zero retries per case. The operational field `attempt_budget: 16` records the total of four held-out cases × two configurations × two attempts per case; `attempt_budget: 16` does not replace the attempts-per-case rule.

The CLI, rather than the student, sets the balanced scheduled-attempt order and the 48-hour operational resume window. The balanced scheduled-attempt order and the 48-hour operational resume window are not additional acceptance conditions or student decision rules.

```powershell
uv run learning-project lab03 freeze --report-dir reports/lab03 `
  --protocol student/lab03/protocol-draft.yaml --by "<student-id>"
$freeze = "<printed-cmp-identifier>"
```

Linux and macOS use `freeze="<printed-cmp-identifier>"`. In both shells, use the complete `cmp-...` identifier printed by `lab03 freeze`.

The freeze binds the exact Variant A and Variant B instructions, intended-factor declaration, protocol, route, development attempt list, and course schemas and contracts. If `lab03 freeze` reports that no unused related-scenario group of held-out cases provided and controlled by the course remains, preserve the development evidence, skip Steps 6–9, record `honest-partial` completion in Step 10 with `stopped_at_step: "Step 5"`, and continue with Step 11 only. Do not create or request a replacement group.

**Expected result:** one immutable freeze manifest exists, and the student has not opened the held-out case files. Capture the `lab03 freeze` result as `reports/lab03/screenshots/03-freeze.png`.

### Step 6: Run the held-out offline comparison

After the freeze, run `select-family`; the CLI assigns one related-scenario group of held-out cases provided and controlled by the course:

```powershell
uv run learning-project lab03 select-family --report-dir reports/lab03 `
  --freeze-id "$freeze" --by "<student-id>"
uv run learning-project lab03 list-positions --report-dir reports/lab03 `
  --freeze-id "$freeze"
```

`list-positions` lists sixteen scheduled attempts: four held-out cases × two configurations × two attempts per case. Run each scheduled attempt in the printed order:

```powershell
uv run learning-project lab03 run --report-dir reports/lab03 --freeze-id "$freeze" `
  --position-id <next-position-id> --adapter openrouter `
  --model-id openrouter/free --by "<student-id>"
```

For every returned response, run:

```powershell
uv run learning-project lab03 structural-check --report-dir reports/lab03 `
  --freeze-id "$freeze" --position-id <returned-position-id>
```

Preserve every scheduled attempt. Do not rerun a scheduled attempt after it has recorded either a returned response or a failure outcome, and do not select the higher-scoring response as the result for a case.

In a fresh terminal, restore `OPENROUTER_API_KEY` and the `$freeze` or `freeze` variable, then recover state with `uv run learning-project lab03 status --report-dir reports/lab03`. The CLI classifies the recorded failure of a started attempt as `route-wide` for authentication failure, quota exhaustion, rate limiting, account-wide denial, or provider-wide unavailability; a timeout remains `position-specific`. Only a recorded `failure_class: route-wide`, also preserved in `route-stop.json`, permits one recovery probe on the next unstarted scheduled attempt within the fixed resume window:

```powershell
uv run learning-project lab03 run --report-dir reports/lab03 --freeze-id "$freeze" `
  --position-id <next-unstarted-position-id> --adapter openrouter `
  --model-id openrouter/free --resume-probe --by "<student-id>"
```

The one permitted recovery probe is not a retry per case: the recovery probe starts the next scheduled attempt rather than replacing the recorded failure outcome of an earlier scheduled attempt. If the route remains unavailable after the recovery probe, close every later unstarted attempt:

```powershell
uv run learning-project lab03 close-unstarted --report-dir reports/lab03 `
  --freeze-id "$freeze" --reason "route unavailable after the permitted probe" `
  --by "<student-id>"
```

Then skip Steps 7–9, record `honest-partial` completion in Step 10 with `stopped_at_step: "Step 6"`, and continue with Step 11 only. Operational recovery preserves evidence but adds no evaluation concept. A comparison with closed unstarted attempts cannot support a bounded configuration decision.

**Expected result for the complete path:** all sixteen scheduled attempts have either a returned outcome or a failed outcome, every returned response has a `structural-check` result, and no attempt identifier was reused. Capture the attempt list as `reports/lab03/screenshots/04-held-out-execution.png`.

### Step 7: Apply absolute assessment with the evaluation rubric

Build the scoring view that withholds variant identity from the human evaluator:

```powershell
uv run learning-project lab03 build-scoring --report-dir reports/lab03 `
  --freeze-id "$freeze"
```

For each `blind-...` item (an anonymous label), compare the structurally valid returned candidate response with the case's supplied source and evaluator-only expected behavior. The expected behavior becomes visible for evaluation only after generation and must never be supplied to Variant A or Variant B. Record one absolute-assessment category. Assign `X` when the proposed text is unreadable or the required source or expected-behavior evidence is missing or unusable, so the response cannot be assessed semantically. An `X` response remains structurally valid but is excluded from the assessable-response count and therefore from the accepted-by-rubric count.

```powershell
uv run learning-project lab03 assess --report-dir reports/lab03 --freeze-id "$freeze" `
  --blind-id <blind-id> --category <S|I|U|Q|R|X> `
  --source-pointer "<exact supplied-source passage>" `
  --rationale "<source- and rubric-based judgment>" --by "<student-id>"
```

Byte-identical response bodies remain separate attempts. A later assessment may use `--shares-rationale-with <earlier-blind-id>` to reuse a rationale, but the command does not merge the attempt records. Failed attempts with no response remain outside the assessable count and do not receive a rubric category. If the supplied source or expected behavior is missing, unusable, or internally inconsistent so that no semantic category can be justified, assign `X`, state the exact evidence defect in the assessment rationale, and later choose `seek-more-evidence` in Step 8. If the evidence still permits a category but exposes a narrower rubric limitation, record the supported category and preserve that limitation in the rationale. Do not invent a separate correction workflow.

**Expected result:** every anonymous label (`--blind-id`) in `scoring-view.json` has one immutable source-grounded assessment; an assessment with category `X` identifies a response that does not enter the assessable-response count.

### Step 8: Aggregate and record the bounded configuration decision

```powershell
uv run learning-project lab03 aggregate --report-dir reports/lab03 `
  --freeze-id "$freeze"
```

For Variant A and Variant B, `aggregate.json` reports five successive count metrics for workflow events. The human-evaluator rubric categories separately provide response-level evidence for the source-support, meaning-coverage, and appropriate-uncertainty criteria. Each successive count is a subset of the preceding count:

1. `attempted`;
2. `returned`;
3. `structurally_valid`;
4. `assessable`;
5. `rubric_acceptable`.

Failure, unstarted, and critical-`U` counts; slice results; differences between the first and second scheduled attempts for the same evaluation case under the same named configuration; latency measured on `timing_boundary`; observed route metadata; and unknown usage values are side evidence, not additional successive denominators. The small designed set creates sampling uncertainty. Different responses from the two attempts on the same case under the same configuration expose generation variability for that case and configuration. One student's judgments do not measure evaluator variability.

Mark the current freeze as the comparison under review, then act as the engineering team and record one outcome from the frozen acceptance conditions, successive counts, critical failures, and unresolved uncertainty:

```powershell
uv run learning-project lab03 select-comparison --report-dir reports/lab03 `
  --comparison-id "$freeze" --by "<student-id>"

uv run learning-project lab03 recommend --report-dir reports/lab03 `
  --freeze-id "$freeze" `
  --outcome <recommend-b|retain-a|reject-both|seek-more-evidence> `
  --rationale "<trace from frozen conditions through counts, blocking conditions, and uncertainty>" `
  --limitations "small designed set;<other limitation>" --by "<student-id>"
```

- `recommend-b`: Variant B satisfies every blocking condition, and Variant B's measured advantages justify the change.
- `retain-a`: A remains acceptable and B does not justify a change.
- `reject-both`: both configurations violate a blocking condition.
- `seek-more-evidence`: relevant evidence or uncertainty remains unresolved.

A higher accepted-by-rubric count cannot override a critical failure that violates a frozen blocking condition. An unknown measurement is not zero. The bounded configuration decision does not authorize deployment or an accepted-knowledge write.

**Expected result:** five successive counts exist for each configuration and one bounded configuration decision is recorded. Capture `reports/lab03/screenshots/05-scoring-recommendation.png`.

### Step 9: Preserve one reviewed regression case

The course's designated human evaluator approved each case-specific expected behavior before generation. The student acting as the human evaluator applies the approved expected behavior in Step 7 and does not retrospectively approve or rewrite the expected behavior after seeing a response.

Acting separately as the engineering team in Step 9, the student traces an unfavorable human-evaluator judgment through the supplied source, approved case-specific expected behavior, model-backed concept-proposal-operation input, returned response, structural result, and evaluation-rubric rule.

The engineering team records an observed response as a configuration defect only when the complete trace confirms that the named configuration produced the semantic failure. If the complete trace instead identifies an evaluator, expected-behavior, reference, or rubric defect, or leaves the defect location unresolved, the engineering team does not promote the observed response to a regression case and uses the authored-fixture branch below for the mandatory regression exercise.

For a confirmed configuration defect, create `student/lab03/regression.yaml` with the original scheduled-attempt and anonymous-label identities:

```yaml
regression_id: <lowercase-slug>
source_kind: observed-failure
position_id: <preserved-position-id>
blind_id: <preserved-blind-id>
diagnosis: <source-grounded failing boundary>
expected_behavior_review: <why the expected behavior remains correct>
reviewed_by: <student-id>
```

If no suitable observed failure exists, use the course-authored fixture in `cases/lab03/authored-failure/authored-failure.json` without claiming model authorship:

```yaml
regression_id: <lowercase-slug>
source_kind: authored-fixture
fixture_id: authored-failure-supported-plus-invented
model_authorship_claim: none
diagnosis: <why the added claim is unsupported>
expected_behavior_review: <supported boundary checked against the fixture source>
reviewed_by: <student-id>
```

```powershell
uv run learning-project lab03 record-regression --report-dir reports/lab03 `
  --record student/lab03/regression.yaml
```

A regression case preserves the reviewed expected-behavior boundary of a known failure for a later regression check. A regression case is not fresh held-out evidence.

**Expected result:** one reviewed regression case exists. Capture `reports/lab03/screenshots/06-regression.png`.

### Step 10: Complete the report and completion record

Complete every applicable section of `reports/lab03/REPORT.md` in Ukrainian and keep every heading. Write in a formal technical style. Use third-person or impersonal constructions; do not use first-person narration such as `я`, `ми`, `мною`, `нами`, `мій`, or `наш`. On the complete path, retain the relative links for screenshots 01–07 before the final commit; the screenshot 07 link points to the final-verification image that Step 11 creates after that commit. An `honest-partial` report removes only links for checkpoints that were not reached and retains the screenshot 07 link.

For the complete path, create:

```yaml
stopped_at_step: "Step 10"
limitation: "none; student-authored evidence is ready for commit-first verification"
preserved_evidence: |
  reports/lab03/
  student/lab03/
```

```powershell
uv run learning-project lab03 record-completion --report-dir reports/lab03 `
  --status complete --detail student/lab03/completion-detail.yaml `
  --by "<student-id>"
```

For an early stop permitted in Step 2, 3, 4, 5, or 6, use the same fields with the exact step named by the applicable stopping branch, the recorded limitation, and the preserved paths, and record `--status honest-partial`. The `record-completion` command writes `reports/lab03/completion-status.yaml`. A partial package must not invent freeze, scoring, decision, or regression artifacts from stages the partial workflow did not reach.

**Expected result:** the report agrees with `completion-status.yaml`.

### Step 11: Commit, verify the exact head, and prepare submission files

```powershell
uv run python -m unittest discover -s tests/public -v
git status --short
git diff --check
git add student/lab03 reports/lab03
git commit -m "feat(lab03): evaluate one instruction change"
git push -u origin HEAD
$finalCommit = git rev-parse HEAD
uv run learning-project lab03 verify --report-dir reports/lab03 `
  --final-commit "$finalCommit"
```

Linux and macOS use `final_commit="$(git rev-parse HEAD)"` and the equivalent `lab03 verify` command.

After verification reports `passed-complete` or `passed-partial`, capture `reports/lab03/screenshots/07-final-verification.png` and generate the Teams report:

```powershell
uv run learning-project prepare-report .\reports\lab03\REPORT.md
git status --short
```

Linux and macOS use `uv run learning-project prepare-report reports/lab03/REPORT.md`.

Do not edit student evidence or amend the commit after verification. Only the Git-ignored `reports/lab03/verification-report.json`, screenshot 07, and generated `reports/lab03/submission/REPORT.md` may differ from the final commit.

**Expected result:** the exact head has a passing verification result and committed evidence remains unchanged.

## Final verification

The complete work is ready for demonstration only when the public tests pass, the report and completion status agree, the exact branch head passes `lab03 verify`, and the post-commit submission files exist without changing committed evidence. `passed-partial` accepts an honest incomplete package for defense of the stopping condition but does not satisfy the complete-laboratory expected result.

## Submission artifacts

Follow [`LABORATORY_STANDING_RULES.md`](../../LABORATORY_STANDING_RULES.md). Submit separately:

- `reports/lab03/submission/REPORT.md`;
- `reports/lab03/verification-report.json`;
- `reports/lab03/screenshots/07-final-verification.png`.

Put the fork URL, personal branch, and exact final commit hash in the Teams cover message. Do not submit credentials, the external vault, unfiltered logs, a PDF duplicate, or unrelated workstation material.

## Control questions

1. Why are judgments on authored fixtures evaluator-preparation evidence rather than model-performance evidence?
2. Why must A and B run on the same held-out cases under one frozen shared experiment protocol?
3. Why are the five successive counts reported separately for each configuration?
4. Why can a higher accepted-by-rubric count not override a critical failure (`U`) that violates a frozen blocking condition?
5. Why is a regression case not fresh held-out evidence?
6. Why does the configuration decision not authorize deployment or a knowledge write?

## Optional extensions

- repair Variant B and perform a regression check on the known regression case;
- freeze a new comparison with a fresh eligible related-scenario group of held-out cases;
- calibrate a binary AI source-support judge against separate source-checked human judgments;
- compare another generator route in a separately frozen experiment that runs both configurations under that route.

Optional work does not replace the mandatory offline comparison, bounded configuration decision, regression case, or final verification.
