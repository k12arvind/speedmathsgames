# AMC 10 Work Summary

## Original Request

The original request was to support Navya's AMC 10 preparation by using the archive linked from:

- `https://www.mathschool.com/blog/competitions/amc-10-problems-and-solutions`

The first concrete task was:

- create a folder called `AMC10 Practice Papers`
- access the AMC 10 papers one by one
- save the materials locally with proper filenames

The longer-term goal was then clarified as:

- combine AMC 10 questions into a usable question bank
- segregate questions topic-wise
- allow topic-wise practice later by:
  - selecting topic
  - selecting number of questions
  - attempting questions first
  - checking solutions after attempting

After that, the immediate implementation focus was narrowed to:

- `Phase 1`: build the database first
- `Phase 2`: topic segregation with an option for manual override later
- UI was explicitly deferred until later

## What Was Created

### 1. Local AMC 10 PDF archive

A local folder was created:

- [AMC10 Practice Papers](/Users/arvind/clat_preparation/AMC10%20Practice%20Papers)

This folder now contains:

- `82` AMC 10 PDF files downloaded from the source page
- `download_manifest.csv`
- `README.md`

At the time of download, the source page exposed AMC 10 materials covering:

- `2000` through `2022`

The source page did not include:

- `2020`

Important context:

- as of `April 26, 2026`, there is no `2026` AMC 10 paper yet because that contest cycle has not occurred

### 2. Dedicated AMC 10 database

A dedicated SQLite database was created:

- [amc10_practice.db](/Users/arvind/clat_preparation/amc10_practice.db)

This database is separate from the existing CLAT/book-practice databases so the AMC data model stays clean and purpose-built.

### 3. AMC 10 parsing and storage module

A new `amc10` module was created:

- [amc10/__init__.py](/Users/arvind/clat_preparation/amc10/__init__.py)
- [amc10/db.py](/Users/arvind/clat_preparation/amc10/db.py)
- [amc10/parser.py](/Users/arvind/clat_preparation/amc10/parser.py)
- [amc10/topics.py](/Users/arvind/clat_preparation/amc10/topics.py)

This module is responsible for:

- contest metadata storage
- parsed question storage
- official solution storage
- auto-topic tagging
- manual topic override support

### 4. Build/import script

A rebuild/import entrypoint was created:

- [scripts/build_amc10_database.py](/Users/arvind/clat_preparation/scripts/build_amc10_database.py)

This script:

- reads the local AMC 10 PDFs
- parses contests
- stores them into `amc10_practice.db`
- applies first-pass topic tagging

### 5. Review and override workflow

Three operational scripts were created:

- [scripts/list_amc10_missing_questions.py](/Users/arvind/clat_preparation/scripts/list_amc10_missing_questions.py)
- [scripts/export_amc10_review_csv.py](/Users/arvind/clat_preparation/scripts/export_amc10_review_csv.py)
- [scripts/import_amc10_topic_overrides.py](/Users/arvind/clat_preparation/scripts/import_amc10_topic_overrides.py)

These support:

- checking contest completeness
- exporting all parsed questions and current tags to CSV
- applying manual topic overrides back into the database

### 6. Topic review CSV

A topic review CSV was generated:

- [amc10_topic_review.csv](/Users/arvind/clat_preparation/amc10_topic_review.csv)

This file is intended for manual review and correction outside the database.

## Current Database Contents

The database currently contains:

- `41` contests
- `1025` questions
- `1025` active topic-tag rows

This matches a full `41 x 25` contest-question set.

## Database Design

The database currently includes these main tables:

### `amc10_contests`

Stores contest-level metadata such as:

- year
- season
- contest code
- contest label
- problems PDF path
- solutions PDF path
- question count
- import status

### `amc10_questions`

Stores question-level data such as:

- contest link
- problem number
- question text
- raw extracted question text
- choices A-E
- correct choice
- official solution
- raw official solution
- page references
- parse status
- parse notes

### `amc10_question_topics`

Stores topic tags such as:

- topic code
- topic name
- subtopic code
- subtopic name
- confidence
- reasoning
- tag source (`auto` or `manual`)
- active/inactive flag

This design allows:

- one initial auto-generated topic assignment
- later manual corrections without deleting history
- future admin/review tooling

## Parsing Strategy Used

### Text extraction approach

The parser uses:

- `PyMuPDF` (`fitz`) as the main extractor
- OCR fallback via `tesseract` for scanned/image-heavy PDFs

This was necessary because the AMC archive is not uniform:

- some files are text-based and parse cleanly
- some older or repackaged files are scan-like or partially image-based
- some later files needed OCR fallback

### Question parsing

The parser attempts to split each contest into question blocks by:

- question number detection
- answer-choice pattern detection

It supports multiple answer formatting patterns, including:

- standard `(A) ... (B) ...`
- OCR-style `A ...` line-based choices

### Solution parsing

The solutions parser extracts:

- problem number
- correct answer letter
- official solution text

### Recovery of missing questions

Four contests initially parsed incompletely because of OCR/text-format edge cases:

- `2009 Contest B`
- `2015 Contest A`
- `2016 Contest A`
- `2016 Contest B`

To close this gap, a fallback mechanism was added:

- if a problem is missing from the problem booklet parse
- but present in the official solutions booklet
- reconstruct the question row from the solution pamphlet prompt section

This recovered `12` missing questions and restored the archive to `1025` questions total.

These recovered rows are marked in the DB with:

- `parse_status = fallback_from_solution`

and have parse notes indicating that they were reconstructed from the official solution pamphlet.

## Topic Classification System

### Purpose

The goal of the first-pass tagging system is not perfect classification.

The goal is:

- create a usable initial draft
- provide confidence and reasoning
- make later review efficient

### Current topic buckets

The current high-level buckets include:

- Geometry
- Algebra
- Number Theory
- Counting and Probability
- Logic and Miscellaneous

### Current subtopic examples

Examples currently in the system include:

- Triangles
- Circles
- Polygons
- Coordinate Geometry
- Solid Geometry
- Linear Equations
- Polynomials
- Functions
- Sequences and Series
- Inequalities
- Divisibility
- Primes
- Digits and Bases
- Counting
- Probability
- Combinatorics
- Logic
- Rates and Word Problems

### Tagging behavior

Each question currently gets:

- one active primary tag
- topic code
- topic name
- subtopic code
- subtopic name
- confidence score
- reasoning text

This is intentionally reviewable rather than “locked.”

## Manual Review Workflow

### Export

To export the current review CSV:

```bash
/usr/local/bin/python3.13 /Users/arvind/clat_preparation/scripts/export_amc10_review_csv.py
```

This writes:

- [amc10_topic_review.csv](/Users/arvind/clat_preparation/amc10_topic_review.csv)

### Review file contents

The CSV includes:

- `question_id`
- `contest_label`
- `year`
- `season`
- `contest_code`
- `problem_number`
- `question_text`
- `correct_choice`
- `official_solution`
- `parse_status`
- `parse_notes`
- `current_topic_code`
- `current_topic_name`
- `current_subtopic_code`
- `current_subtopic_name`
- `confidence`
- `reasoning`
- `tag_source`

And blank override columns:

- `override_topic_code`
- `override_topic_name`
- `override_subtopic_code`
- `override_subtopic_name`
- `override_reasoning`

### Import overrides

After editing the override columns, import them with:

```bash
/usr/local/bin/python3.13 /Users/arvind/clat_preparation/scripts/import_amc10_topic_overrides.py
```

This does not overwrite the original auto row destructively.

Instead it:

- deactivates the current active tag for that question
- inserts a new active manual tag

This keeps the database compatible with future admin/review tooling.

## Completeness Check Workflow

To verify whether any contest is missing questions:

```bash
/usr/local/bin/python3.13 /Users/arvind/clat_preparation/scripts/list_amc10_missing_questions.py
```

At the current state, this script returns no missing questions.

## Current Known Limitations

The current system is functional, but not final-quality in all respects.

### 1. Some question rows still need human review

Although all `1025` question rows exist, some rows were produced from OCR or fallback reconstruction and should be reviewed before relying on them in a student-facing practice UI.

### 2. Topic tagging is first-pass only

The current tags are intentionally heuristic. They are useful for:

- sorting
- bulk review
- first-pass filtering

But they are not yet trustworthy enough to be considered final without review.

### 3. Some tags are generic

Some questions currently land in:

- `Logic and Miscellaneous`
- `Unclassified`

These should be reduced through manual review and a second-pass refinement step.

### 4. No AMC practice UI yet

The user explicitly chose to defer the UI. So there is currently:

- no topic-selection screen
- no practice session flow
- no answer submission screen
- no solution reveal screen

Only the data layer and review workflow are in place.

## Recommended Next Steps

The recommended next steps are:

### 1. Manual review pass on the CSV

First review:

- low-confidence tags
- `fallback_from_solution` rows
- `Logic and Miscellaneous / Unclassified` rows

### 2. Improve the taxonomy and tagging rules

After the first review pass, refine the topic system by:

- tightening topic definitions
- adding subtopics where needed
- reducing generic buckets
- improving rule coverage

### 3. Add difficulty classification

Once topics are stable, add fields for:

- difficulty band
- maybe estimated AMC-level difficulty by problem number or content

### 4. Build the practice backend

Only after the data is stable:

- topic selection
- question-count selection
- attempt tracking
- reveal solutions after submission
- Navya-specific progress tracking

### 5. Build the UI later

UI should be built after the data and review pipeline are trusted.

## Files Added or Updated

### Added

- [amc10/__init__.py](/Users/arvind/clat_preparation/amc10/__init__.py)
- [amc10/db.py](/Users/arvind/clat_preparation/amc10/db.py)
- [amc10/parser.py](/Users/arvind/clat_preparation/amc10/parser.py)
- [amc10/topics.py](/Users/arvind/clat_preparation/amc10/topics.py)
- [scripts/build_amc10_database.py](/Users/arvind/clat_preparation/scripts/build_amc10_database.py)
- [scripts/list_amc10_missing_questions.py](/Users/arvind/clat_preparation/scripts/list_amc10_missing_questions.py)
- [scripts/export_amc10_review_csv.py](/Users/arvind/clat_preparation/scripts/export_amc10_review_csv.py)
- [scripts/import_amc10_topic_overrides.py](/Users/arvind/clat_preparation/scripts/import_amc10_topic_overrides.py)
- [docs/AMC10_WORK_SUMMARY.md](/Users/arvind/clat_preparation/docs/AMC10_WORK_SUMMARY.md)

### Created/generated outputs

- [AMC10 Practice Papers](/Users/arvind/clat_preparation/AMC10%20Practice%20Papers)
- [amc10_practice.db](/Users/arvind/clat_preparation/amc10_practice.db)
- [amc10_topic_review.csv](/Users/arvind/clat_preparation/amc10_topic_review.csv)

## Command Reference

### Rebuild AMC 10 database

```bash
/usr/local/bin/python3.13 /Users/arvind/clat_preparation/scripts/build_amc10_database.py
```

### Export review CSV

```bash
/usr/local/bin/python3.13 /Users/arvind/clat_preparation/scripts/export_amc10_review_csv.py
```

### Import manual topic overrides

```bash
/usr/local/bin/python3.13 /Users/arvind/clat_preparation/scripts/import_amc10_topic_overrides.py
```

### Check for missing questions

```bash
/usr/local/bin/python3.13 /Users/arvind/clat_preparation/scripts/list_amc10_missing_questions.py
```

## Summary

Up to this point, the work completed is:

- downloaded and organized the AMC 10 PDF archive locally
- created a dedicated AMC 10 SQLite database
- parsed contests into structured question rows
- attached official solutions and correct answers
- implemented OCR fallback where needed
- recovered missing questions from official solution pamphlets
- built a first-pass topic tagging system
- generated a manual review CSV
- added manual topic override import support

This means the project has now completed the core of:

- `Phase 1`: build the AMC 10 database
- `Phase 2`: topic segregation with later manual override support

The next major stage is data review and refinement, followed by the eventual practice workflow and UI.
