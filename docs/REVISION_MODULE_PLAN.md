# Revision Module — Detailed Implementation Plan

**Date**: 20 April 2026
**Status**: Planning — awaiting feedback before implementation

---

## Current State (What We Have)

| Data | Count |
|---|---|
| HTML article sections | 2,233 (across 168 PDFs) |
| Total questions (with MCQ choices) | 16,105 |
| PDFs with questions generated | 195 |
| Test sessions completed | 57 |
| Question attempts recorded | 1,559 |
| PDFs tested at least once | 38 of 195 (19%) |

**Key gap**: 157 PDFs (81%) have questions but have NEVER been tested. Of the 38 tested, none have been RE-tested. Zero revision activity exists today.

---

## The Revision Cycle

```
Day 1: READ new PDF → TAKE TEST → System records section-level scores
                                   ↓
Day 2-3: System shows "Due for revision" → RE-READ weak sections → RE-TEST
                                   ↓
Day 7: System shows "Weekly review" → QUICK RE-READ → RE-TEST
                                   ↓
Day 14-30: System shows "Monthly refresh" → SKIM → RE-TEST (only weak items)
                                   ↓
Repeat cycle — intervals grow as mastery improves
```

**Key principle**: RE-READ first, then RE-TEST. Tests alone don't help — she must engage with the content before verifying recall.

---

## Database Schema

### New table: `revision_schedule`

Tracks the SRS state of each SECTION (not each question — sections are the revision unit because she needs to re-read the source material, not just re-answer individual questions).

```sql
CREATE TABLE revision_schedule (
    schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- What to revise
    pdf_filename TEXT NOT NULL,
    section_index INTEGER NOT NULL,
    section_title TEXT,
    category TEXT,
    
    -- Reading tracking
    first_read_date DATE,          -- when she first read this section
    last_read_date DATE,           -- most recent reading
    total_reads INTEGER DEFAULT 0, -- how many times she's read it
    
    -- Test tracking (section-level, not question-level)
    last_test_date DATE,
    last_test_accuracy REAL,       -- 0-100, section accuracy from last test
    best_test_accuracy REAL,
    total_tests INTEGER DEFAULT 0,
    
    -- SRS scheduling
    revision_level INTEGER DEFAULT 0,  -- 0=new, 1=good, 2=fair, 3=needs revision, 4=must revise
    current_interval_days INTEGER DEFAULT 1,
    next_review_date DATE,             -- when this section is due for review
    
    -- Status
    is_mastered BOOLEAN DEFAULT 0,     -- accuracy ≥85% for 3+ consecutive tests
    consecutive_good_tests INTEGER DEFAULT 0,
    
    UNIQUE(pdf_filename, section_index)
);

CREATE INDEX idx_revision_next_date ON revision_schedule(next_review_date);
CREATE INDEX idx_revision_level ON revision_schedule(revision_level);
CREATE INDEX idx_revision_category ON revision_schedule(category);
```

---

## SRS Interval Logic

### After she READS a section + TAKES a test:

| Test accuracy | What it means | Next interval | Consecutive good resets? |
|---|---|---|---|
| 85-100% | She remembers well | Current interval × 2 (max 60 days) | No — increment consecutive_good |
| 70-84% | Partial recall | 7 days | Reset to 0 |
| 50-69% | Weak recall | 3 days | Reset to 0 |
| Below 50% | Didn't remember | 1 day (re-read tomorrow) | Reset to 0 |

### After she READS but does NOT test:

| Action | Next interval |
|---|---|
| Clicked "Mark as Revised" | 7 days |
| Just scrolled through (view session tracked) | 5 days |

### Mastery threshold:

A section is marked **"mastered"** when:
- `consecutive_good_tests >= 3` (scored 85%+ three times in a row)
- At that point, interval becomes 60 days (monthly maintenance)
- If she scores < 85% on a mastered section, it loses mastery status and resets

### Initial schedule (first time reading a PDF):

When she reads a new PDF for the first time:
- All sections start with `next_review_date = first_read_date + 1 day`
- She's expected to take a test within 48 hours (the critical window from forgetting curve research)

---

## Category Weighting

Based on CLAT exam pattern (5-year analysis) + her current weakness:

| Category | CLAT Weight | Her Accuracy | Priority Multiplier | Explanation |
|---|---|---|---|---|
| Polity & Constitution | 22% | 85.8% | 1.3x | Highest CLAT share |
| International Affairs | 21% | 86.7% | 1.3x | Highest CLAT share |
| Supreme Court / HC | Law exam | 79.5% | 1.3x | Law entrance + weakest category |
| Economy & Business | 14% | 80.1% | 1.2x | High CLAT share + weak |
| Environment & Science | 11% | 82.6% | 1.1x | Mid share + below target |
| Awards / Sports / Defence | 9% | 81.3% | 1.0x | Low CLAT share + weak |
| Government Schemes | 9% | 85.3% | 1.0x | Mid accuracy |
| Static GK | 8% | 87.2% | 0.8x | Declining in CLAT + strong |

**Usage**: When the daily revision queue has more sections due than she can review in one sitting (~30 min), the system picks sections from higher-weighted categories first.

---

## Revision Dashboard Page

### Page: `revision_dashboard.html`

### Layout

```
┌─────────────────────────────────────────────────────────────┐
│  Smart Revision Dashboard                    [Dashboard] [Home] │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐         │
│  │  12  │  │  5   │  │ 38m  │  │  83% │  │  4🔥 │         │
│  │  Due │  │Overdue│  │ Est. │  │ Avg  │  │Streak│         │
│  │Today │  │      │  │ Time │  │ Acc  │  │      │         │
│  └──────┘  └──────┘  └──────┘  └──────┘  └──────┘         │
│                                                             │
│  ═══ Today's Revision Queue ═══                             │
│                                                             │
│  ┌─ 🔴 Must Revise ─────────────────────────────────────┐  │
│  │                                                       │  │
│  │  1. Arab League — Static GK facts (Apr 6 PDF)        │  │
│  │     Last read: 14d ago · Last test: 50% · Due: 3d ago│  │
│  │     [📖 Read Section] [✅ Mark Revised]               │  │
│  │                                                       │  │
│  │  2. SC Cooperative Society ruling (Apr 13 PDF)       │  │
│  │     Last read: 7d ago · Last test: 50% · Due: today  │  │
│  │     [📖 Read Section] [✅ Mark Revised]               │  │
│  │                                                       │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌─ 🟣 Needs Revision ──────────────────────────────────┐  │
│  │                                                       │  │
│  │  3. FAO Food Price Index (Apr 6 PDF)                 │  │
│  │     Last read: 14d ago · Last test: 67% · Due: today │  │
│  │     [📖 Read Section] [✅ Mark Revised]               │  │
│  │                                                       │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌─ 🔵 Weekly Review ───────────────────────────────────┐  │
│  │                                                       │  │
│  │  4. Gujarat HC AI Policy (Apr 6 PDF)                 │  │
│  │     Last read: 14d ago · Test: 92% · Due: today      │  │
│  │     [📖 Read Section] [✅ Mark Revised]               │  │
│  │                                                       │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  After revising, verify your recall:                 │   │
│  │  [📝 Take Revision Test — 15 questions from above]   │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                             │
│  ═══ Category Health ═══                                    │
│                                                             │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐              │
│  │ Economy 🔴 │ │ SC/HC  🔴 │ │ Awards 🟡 │              │
│  │ 80.1%      │ │ 79.5%     │ │ 81.3%     │              │
│  │ 8 due      │ │ 4 due     │ │ 6 due     │              │
│  │ Stale: 12d │ │ Stale: 7d │ │ Stale: 5d │              │
│  └────────────┘ └────────────┘ └────────────┘              │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐              │
│  │ Env/Sci 🟡 │ │ Intl  🟢 │ │ Polity 🟢 │              │
│  │ 82.6%      │ │ 86.7%     │ │ 85.8%     │              │
│  │ 3 due      │ │ 2 due     │ │ 1 due     │              │
│  │ Stale: 3d  │ │ Stale: 2d │ │ Stale: 1d │              │
│  └────────────┘ └────────────┘ └────────────┘              │
│                                                             │
│  ═══ Revision Progress ═══                                  │
│                                                             │
│  Total sections: 2,233                                      │
│  ████████████░░░░░░░░░░░░░░░░  38% read at least once      │
│  ████░░░░░░░░░░░░░░░░░░░░░░░░  15% tested                  │
│  ██░░░░░░░░░░░░░░░░░░░░░░░░░░   5% mastered                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## "📖 Read Section" Flow

When she clicks "Read Section" on a revision item:

1. Opens `article_viewer.html?pdf=<filename>#section-<index>`
2. Scrolls directly to that specific section
3. View tracking starts (section-level IntersectionObserver + active time)
4. Her existing highlights and notes are shown
5. She reads, possibly adds new highlights/notes
6. When she navigates back, the system records:
   - `last_read_date = today`
   - `total_reads += 1`
   - Reading time captured via view session

---

## "📝 Take Revision Test" Flow

After she's done reading the due sections:

1. Clicks "Take Revision Test" on the revision dashboard
2. System collects questions ONLY from the sections she just revised today
   - Pulls question IDs by matching section SIDs to questions in `questions` table
   - Limits to ~20 questions if too many sections (weighted by priority)
3. Uses the existing assessment test flow (`assessment.html`)
4. After the test, for each section:
   - Calculate section-level accuracy from this test
   - Update `revision_schedule`: `last_test_date`, `last_test_accuracy`, intervals
   - If accuracy ≥ 85%: increment `consecutive_good_tests`, double interval
   - If accuracy < 85%: reset `consecutive_good_tests`, shorten interval
5. Results screen shows per-section improvement:
   ```
   Arab League (Static GK):     50% → 80%  ↑ Improving!
   FAO Food Price Index:        67% → 90%  ↑ Great!
   SC Cooperative ruling:       50% → 45%  ↓ Needs more revision
   ```

---

## Auto-Population

### When does `revision_schedule` get populated?

**Trigger 1: After a test** (most common)
- When a test completes, the system runs section analysis on that PDF
- For each section with test data, creates/updates a `revision_schedule` row
- Sets `next_review_date` based on accuracy

**Trigger 2: After reading** (via view session)
- When she reads a PDF in the HTML viewer and the view session completes
- Sections she scrolled through get a `revision_schedule` row with
  `first_read_date = today`, `next_review_date = today + 1 day`
- This prompts her to take a test the next day

**Trigger 3: Manual "Mark as Revised"**
- She clicks "Mark as Revised" on a section without taking a test
- Updates `last_read_date`, sets `next_review_date = today + 7 days`

---

## Daily Cron (optional, Phase 2)

A lightweight script that runs daily to:
1. Count overdue sections → used for the "Overdue" stat on the dashboard
2. Send a daily digest (optional): "You have 8 sections due for revision today"
3. Flag sections that have been overdue > 14 days as "stale" (bumps their priority)

---

## Revision Compilation Page (Phase 3)

### Page: `revision_compilation.html`

A single scrollable page that compiles ALL sections due for revision:

1. Query: `SELECT * FROM revision_schedule WHERE next_review_date <= today ORDER BY revision_level DESC, category_weight DESC`
2. For each section: pull HTML content from `html_articles` + annotations from `html_annotations`
3. Render them all in one page with:
   - Section performance badges (accuracy, level, last read)
   - "Mark as Revised" per section
   - Inline test questions per section (expandable)
4. Filters: by category, by urgency level, by date range

**This is the "generate a revision PDF" feature — but as a live HTML page instead.**

---

## What We're NOT Building (Keeping It Simple)

- ❌ No email/push notifications (she'll just open the dashboard)
- ❌ No spaced repetition at the QUESTION level (too granular — sections are the unit)
- ❌ No AI-powered "predict what she'll forget" (the SRS intervals are good enough)
- ❌ No gamification (points, badges, leaderboards — not useful for exam prep)
- ❌ No daily time goals ("study 30 min/day" targets — she's self-motivated)

---

## Implementation Phases

### Phase 1: Foundation (Build First)
1. Add view tracking to `article_viewer.html` (IntersectionObserver per section)
2. Create `revision_schedule` table
3. Auto-populate schedule after tests (hook into test completion)
4. Auto-populate schedule after reading (hook into view session completion)

### Phase 2: Revision Dashboard
5. Build `revision_dashboard.html` with:
   - Today's revision queue (grouped by urgency)
   - Category health grid
   - Progress bars
6. "📖 Read Section" flow (deep-link to article viewer at specific section)
7. "✅ Mark as Revised" flow (updates schedule)

### Phase 3: Revision Testing
8. "📝 Take Revision Test" — generates test from today's revised sections
9. Post-test SRS interval updates
10. Per-section improvement comparison (before vs after)

### Phase 4: Compilation
11. Revision compilation page (all due sections in one scrollable view)
12. Category deep-dive filters
13. "Re-test this PDF" flow

---

## Success Metrics

After 30 days of use, we should see:
- **Revision coverage**: >60% of read sections have been revised at least once
- **Accuracy improvement**: sections that were < 70% on first test improve to > 80% on re-test
- **Retention**: re-test scores on 14-day-old material stay above 75% (vs ~15% without revision)
- **Daily engagement**: revision dashboard visited 5+ days/week
- **Category balance**: no category goes > 14 days without revision

---

## Open Questions for Review

1. **Daily quota**: Should we cap "Today's Queue" at a specific number (e.g., max 10 sections)? Or show everything due and let her prioritize?

2. **New vs revision balance**: When she has new PDFs to read AND old sections to revise, should the dashboard suggest a ratio (e.g., "Read 1 new PDF, then revise 5 old sections")?

3. **Section granularity**: Current sections are topic-level (~10-12 questions each). Is this the right unit, or should some sections be split further (e.g., "About BRO" and "BRO Statistics" as separate items)?

4. **Mastery display**: Should mastered sections be hidden from the dashboard entirely, or shown in a collapsed "Mastered" section for confidence?

5. **Weekend behavior**: Should weekends have a lighter revision load, or same as weekdays?
