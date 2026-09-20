# Laboratory 01 Report

## Summary

This Laboratory 01 run establishes the governed AI system boundary artifacts in the
student-owned project paths `reports/lab01/` and `student/design/`.

Important limitation: the evidence host is macOS / Darwin. The lab instructions classify macOS
as a red preflight host, so this is a complete repository workflow run but not a green supported
Windows/Linux workstation run.

## Repository And Branch

- Fork URL: `https://github.com/AntonHritsai/ai-systems-design-course`
- `origin`: `https://github.com/AntonHritsai/ai-systems-design-course.git`
- `upstream`: `https://github.com/sobol-mo/ai-systems-design-course.git`
- Branch: `lab01/anton-hritsai`
- Student-owned committed paths: `training-project/reports/lab01/` and
  `training-project/student/design/`

## Workstation Evidence

The current workstation evidence is preserved in `environment-report.json`, `provision.log`, and
the screenshots under `screenshots/`.

Observed tools:

- Git: `git version 2.54.0 (Apple Git-157)`
- GitHub CLI: `gh version 2.101.0 (2026-09-15)`
- uv: `uv 0.12.15 (Homebrew 2026-09-15 aarch64-apple-darwin)`
- Obsidian: `1.13.7`
- Antigravity CLI: unavailable (`agy: command not found`)

The second supported Windows `winget configure` convergence run was not performed because this
evidence run is on macOS. The closest local evidence is the repeated tool capability checks and
the final `learning-project doctor` report, which remains red because the host is unsupported.

## External Vault

External vault path: `/Users/antonygritsai/Desktop/Sobol/ai-systems-learning-vault`

The vault is outside the Git repository and contains:

- `README.md`
- `sources/module-01-ai-engineering-foundations.md`

The source record uses course commit `e4fb5c6bbb2cb150c6000ed1406dff10b6854690` and course path
`modules/01_AI_Engineering_Foundations/01_AI_Engineering_Foundations_Theory.md`.
The external vault is shown in `screenshots/17-vault-in-obsidian.png`, and the raw YAML front
matter is shown in `screenshots/18-vault-yaml-source.png`.

Off-device backup/sync was not verified on this Mac run. For a supported final workstation run,
the vault should be placed in OneDrive or another existing off-device backup/sync location.

## Proposer Path

Antigravity CLI was not available on this host. The proposal was completed by the student through
the documented no-agent/manual fallback. This fallback does not claim live separation between an
AI proposer and the student reviewer. The planned ordinary governance boundary remains: AI may
propose, deterministic workflow validates and applies only approved content, and the student keeps
semantic approval authority.

## Personal Domain Boundary

The selected `personal_domain` is `Backend API design for educational projects`. It is only a
non-sensitive possible later extension. It does not redefine the fixed course system, which remains
a workstation-local AI-assisted learning knowledge system for technical concepts.

## Usefulness, Baseline, And Trade-Off

AI can be useful because it can draft bounded candidate interpretations and expose uncertainty
from supplied evidence. The simpler non-AI baseline is a manual Markdown source log plus Git
commits and deterministic validation. That baseline preserves provenance and audit evidence, but
it does not help draft candidate interpretations.

The main design trade-off is speed versus authority control. Requiring human review and a
digest-bound decision slows down accepted changes, but it reduces the risk that a fluent but
unsupported proposal becomes accepted state.

## Semantic Review For Step 8

1. Yes. The proposal preserves the supplied learning knowledge system; the personal domain is only a bounded future extension.
2. Yes. The learning outcome describes an observable student capability: tracing a concept to a source, explaining authority boundaries, and preserving review/approval evidence.
3. Yes. The non-goals exclude production knowledge-platform implementation, graph/vector indexes, private-data ingestion, high-consequence decisions, and redefining the system identity.
4. Yes. The governance fields limit AI to proposing, assign structural checks and digest binding to deterministic commands, and leave semantic approval to the student.
5. Yes. The usefulness condition can be checked through preserved evidence: environment setup, source commit, validation, refused premature apply, decision, and accepted contract.
6. Yes. The material risk is plausible: a structurally valid but semantically overbroad proposal could be mistaken for a good design.
7. Yes. The baseline is simpler: manual Markdown logging plus Git and validation. It covers provenance and evidence without AI-assisted drafting.
8. Yes. Required evidence includes deterministic results and human semantic review/source grounding.
9. Yes. The uncertainty states that future grounding quality is not yet established once the vault grows beyond the first source.

Conclusion: the proposal is acceptable for approval after successful deterministic validation.

## Verification Summary

- `uv sync` completed successfully.
- Lab01-specific public tests passed: `Ran 18 tests`, `OK`.
- Full `unittest discover -s tests/public -v` reaches Lab02 tests that reference Module 02 files
  not present in this published tree; no upstream-owned files were added or modified to hide that.
- Starter proposal validation succeeded in Step 6.
- Premature `apply` before `boundary-decision.json` failed as expected.
- Final proposal validation succeeded for `lab01-learning-boundary-backend-api-design`.
- `boundary-decision.json` records `approved` and proposal digest
  `d36cb7f76acdf8360eda32307d3d4ba98957326cf9aae681132cc5fda3f6f7ab`.
- `student/design/learning-system-boundary.yaml` records `status: approved` and the same proposal
  digest in its `accepted` section.
- Final verification reran Lab01 tests, `doctor`, `validate`, `apply`, JSON parsing, remotes,
  branch, `git diff --check`, and clean status.

## Recovery Plan

- Reproducible environment: rerun the supported Windows/Linux provisioning path and `uv sync`.
- Git-backed project artifacts: restore from the submitted fork, branch, and commit.
- External Markdown vault: restore from the off-device synchronized or backed-up vault location.

## Screenshot Evidence

The screenshot set is stored under `reports/lab01/screenshots/`. See
`reports/lab01/screenshots/README.md` for the filename-to-evidence mapping.

## Why Schema Validation Is Not Enough

Schema validation checks required fields, simple formats, and workflow invariants. It cannot prove
that the proposal preserves the intended system identity, uses the personal domain correctly,
states a meaningful usefulness condition, or identifies the right risk. Those judgments require
human semantic review against the supplied theory and project contracts.
