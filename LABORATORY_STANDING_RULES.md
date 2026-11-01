# Laboratory standing rules

These rules apply to every laboratory in this course. Each laboratory file adds only the artifacts, screenshot filenames, and report sections that are specific to that exercise. The due date of a laboratory is the due date of the corresponding Microsoft Teams assignment.

The student reads these rules together with the laboratory being performed. Microsoft Teams does not add further academic rules.


## Workstation rights

Every Windows student in this course works with a local administrator account. Laboratory commands may create directories, install project dependencies with `uv`, and write under the repository tree. The instructions assume those rights and are not adapted for limited Windows accounts. Linux and macOS students need equivalent rights to install dependencies and write under the repository tree.

## Report content

The report records the work that was performed, not only the final results. It describes the course of execution in enough detail that another reader can follow what was done, in which order, and why.

The supplied `REPORT.md` is an instructional template. Its opening directions and section prompts tell the student what content to write; they are not report content. Before submission, the student replaces or removes every instructional prompt while preserving all supplied report headings.

The report is formal technical documentation. It uses third-person or impersonal constructions and does not use first-person narration such as `я`, `ми`, `мною`, `нами`, `мій`, `наш`, or equivalent first-person forms. For example, the report states that "студент виконав перевірку", "перевірку виконано", or "результат підтверджує", rather than "я виконав перевірку" or "ми отримали результат".

Every report must contain a `Мета роботи` section near the beginning and a `Висновки` section at the end. `Мета роботи` states the desired capability or system state from the laboratory rather than listing the procedure. `Висновки` identifies what the student completed and obtained, then explicitly states whether the goal was achieved fully, achieved partially, or not achieved. That judgment must refer to the report evidence. For a partially achieved or unachieved goal, the conclusions also identify the missing result and its reason.

Every report contains the heading `Хід виконання` between `Мета роботи` and `Висновки`. Its checkpoint subsections follow the published student steps, explain the performed action, observed result, and reason for continuation, and include the screenshot named for that checkpoint by the laboratory. Labels used only to develop the course material, such as `Authoring Stage B`, `C1`, or `C2`, are not student execution stages and must not appear in the report.

A report without either mandatory section, without an explicit goal-attainment judgment in `Висновки`, or written as a first-person narrative is incomplete and is returned for correction.

The report includes every required checkpoint screenshot named in that laboratory, including its final-verification screenshot. Each screenshot must uniquely identify the author and the date of capture: the operating-system account or GitHub login and the system date must be visible in the image (`Get-Date` or `date` in the same terminal, or the visible clock). A caption in the report does not replace that visible identification. A screenshot records the student's own execution; an authored illustration, copied output, or placeholder image is not a checkpoint screenshot.

The submitted package identifies the student's GitHub fork, personal branch, and complete commit hash. Normally all three appear in the report identity section. When a laboratory explicitly uses commit-first verification and therefore cannot place a commit's own hash inside that commit, the committed source report contains the fork and branch, while the generated verification evidence contains the complete final hash. No separate Microsoft Teams cover message or text-field notification is required; the student attaches only the files listed by that laboratory.

A one-page report cannot receive a high mark.

The submitted narrative report is written in Ukrainian.

## Submission

Reports are uploaded to the corresponding Microsoft Teams assignment. The narrative report is one Markdown file named `REPORT.md`. That file is attached directly; a link is not a submission.

The laboratory may also require a small set of machine-readable evidence files. Those files are attached individually. An archive is not accepted.

The source report in Git uses relative Markdown image paths into `reports/labNN/screenshots/`; this is the report viewed on GitHub. The Teams narrative file is the copy produced by `learning-project prepare-report`, which embeds those images so Teams can render one Markdown attachment. The student runs that command as written in the laboratory. The generated `reports/labNN/submission/REPORT.md` is an ignored attachment for Microsoft Teams and is not committed to the fork.

## Academic integrity

Reports that show plagiarism, copying, or identity with another student's work are not accepted for credit.

Using the course-documented agent path to draft a laboratory proposal is not plagiarism. Copying another student's report, screenshots, or machine-readable artifacts is.

## Recording of results

After successful defence of all laboratories at the end of the semester, grades are transferred into the academic group's grade record.

## Deadlines

Each laboratory has a deadline: the due date of its Microsoft Teams assignment. Missing that deadline reduces the grade by one point. Work submitted after the credit week may be reviewed in the following semester.

Work is accepted one laboratory at a time.
