# Smart Revision Engine — Requirements Document

**Project**: speedmathsgames.com GK Module
**Date**: 20 April 2026
**Status**: Design approved, sample validation in progress

---

## 1. Problem Statement

Saanvi reads daily/weekly/monthly current affairs PDFs, takes tests immediately after reading (scoring 80-87%), and **never revisits** the material. Without systematic revision, research shows 85-90% of current affairs facts are forgotten within 7 days. With 16,000+ questions across 8 categories, she needs a system that tells her **what to re-read, when, and tracks whether revision actually helped**.

### Key Insight
The revision cycle must be **Read → Test → Identify gaps → Re-read gaps → Re-test**. Tests alone don't help — she must re-read the source material first, then test to verify retention.

---

## 2. Architecture Decision: Shift from PDF to HTML

### Why
- Daily/weekly PDFs are **pure text** (zero images) with clean structured formatting
- HTML enables: semantic sections, text highlighting, inline notes, inline testing, responsive mobile, full-text search, and trivial revision compilation
- PDF canvas annotations (x,y coordinates) don't survive cross-document compilation; HTML text-range annotations do

### Migration Strategy
- **New PDFs**: convert to HTML at upload/processing time
- **Old PDFs with annotations**: keep PDF viewer (don't migrate annotations)
- **Both viewers coexist** — old content stays PDF, new content served as HTML
- **Section-level operations** (color-coding, testing, revision tracking) work identically in both viewers

### What Changes for the User
| Feature | PDF (old) | HTML (new) |
|---|---|---|
| Free-form pen drawing | ✅ | ❌ (replaced by text highlighting) |
| Text highlighting (like Kindle) | ❌ | ✅ |
| Typed notes on paragraphs | ❌ | ✅ (inline, searchable) |
| Annotations survive compilation | ❌ | ✅ |
| Section-level deep linking | ❌ | ✅ |
| Mobile responsive | ❌ | ✅ |
| Inline "Test This Section" | ❌ | ✅ |

---

## 3. PDF → HTML Conversion

### Input
LegalEdge / Career Launcher daily/weekly/monthly current affairs PDFs (3-25 pages, pure text, structured with colored section headers).

### Output
Semantic HTML stored in database, one row per section:

```html
<article data-pdf="current_affairs_2026_april_6.pdf" data-date="2026-04-06">
  <section id="sec-1" data-category="Government Schemes & Reports"
           data-sid="legaledge_2026-april-6_0001">
    <h2>Sadhana Saptah 2026 Launched to Boost Governance and Service Delivery</h2>
    <p class="in-the-news">In the News: India launched Sadhana Saptah 2026...</p>
    <h3>Key Points:</h3>
    <ul>
      <li><strong>About Sadhana Saptah:</strong> SADHANA stands for...</li>
      <li><strong>Mission Karmayogi:</strong> Central Sector Scheme launched...</li>
    </ul>
  </section>
  <section id="sec-2" data-category="Awards / Sports / Defence" ...>
    ...
  </section>
</article>
```

### Conversion Rules
- 14pt+ bold white text → category header (National/International/Economy etc.)
- 12pt bold colored (#c0392b) text → section title (`<h2>`)
- "In the News:" prefix → lead paragraph
- "Key Points:" → `<h3>` + `<ul>` for bullets
- 9-10pt body → `<p>` paragraphs
- Bullet points (•) → `<li>` items
- Bold spans within body → `<strong>`
- Preserve original colors as CSS classes for visual fidelity

### Storage
New table `html_articles`:
```sql
CREATE TABLE html_articles (
    article_id INTEGER PRIMARY KEY,
    pdf_filename TEXT NOT NULL,
    section_index INTEGER NOT NULL,
    section_title TEXT,
    category TEXT,
    sid_prefix TEXT,           -- links to question SIDs
    html_content TEXT NOT NULL,
    plain_text TEXT,           -- for search
    page_number INTEGER,       -- original PDF page
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(pdf_filename, section_index)
);
```

---

## 4. HTML Article Viewer

### Page: `article_viewer.html?pdf=current_affairs_2026_april_6.pdf`

### Layout
```
┌─────────────────────────────────────────────────────┐
│ Header: PDF name, date, category tabs               │
├─────────────────────────────────────────────────────┤
│ ┌─ Section 1 ─────────────────────────────────────┐ │
│ │ 🟢 Good (90%) [color bar]                       │ │
│ │ Government Schemes & Reports                     │ │
│ │ ┌───────────────────────────────────────────────┐│ │
│ │ │ Sadhana Saptah 2026 Launched...               ││ │
│ │ │ In the News: India launched...                ││ │
│ │ │ Key Points:                                   ││ │
│ │ │ • About Sadhana Saptah: ...                   ││ │
│ │ │ • Mission Karmayogi: ...                      ││ │
│ │ │ [highlighted text by user]                    ││ │
│ │ │ 📝 User note: "Remember 3 Sutras"            ││ │
│ │ └───────────────────────────────────────────────┘│ │
│ │ [✅ Mark as Revised] [📝 Test This Section]     │ │
│ └─────────────────────────────────────────────────┘ │
│ ┌─ Section 2 ─────────────────────────────────────┐ │
│ │ 🟣 Needs Revision (55%) [color bar]             │ │
│ │ ...                                              │ │
│ └─────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

### Annotation Features
1. **Text highlighting**: select text → toolbar appears → choose color (yellow/green/pink) → highlight saved
2. **Inline notes**: click any paragraph → "Add note" tooltip → type note → saved below the paragraph
3. **Storage**: `html_annotations` table with `article_id, section_index, annotation_type, start_offset, end_offset, text_content, color, created_at`

### Section Features
- Color bar on left (red/purple/blue/green/grey) based on test performance
- Accuracy badge: "90% · Good" or "Not tested"
- "Mark as Revised" button → records revision timestamp, pushes SRS interval
- "Test This Section" button → starts a mini-test with questions from this section only

---

## 5. Spaced Repetition Engine

### Table: `revision_schedule`
```sql
CREATE TABLE revision_schedule (
    schedule_id INTEGER PRIMARY KEY,
    pdf_filename TEXT NOT NULL,
    section_index INTEGER NOT NULL,
    section_title TEXT,
    category TEXT,
    first_read_date DATE,
    last_read_date DATE,
    last_test_date DATE,
    last_test_accuracy REAL,
    revision_level INTEGER DEFAULT 0,  -- 0-4 scale
    interval_days INTEGER DEFAULT 1,
    next_review_date DATE,
    total_reads INTEGER DEFAULT 0,
    total_tests INTEGER DEFAULT 0,
    is_mastered BOOLEAN DEFAULT FALSE,
    UNIQUE(pdf_filename, section_index)
);
```

### SRS Logic (Read-First)

After she reads a section + takes a test:

| Scenario | Next review interval |
|---|---|
| Read + tested 85%+ | Current interval × 2 (max 60 days) |
| Read + tested 70-84% | 7 days |
| Read + tested 50-69% | 3 days |
| Read + tested <50% | 1 day (re-read tomorrow) |
| Read but NOT tested | 7 days |
| NOT read, overdue | Stays on daily list until read |

Initial intervals after first read: 1d → 3d → 7d → 14d → 30d → 60d

### Category Weighting (CLAT exam pattern)
| Category | Weight | CLAT share |
|---|---|---|
| Polity & Constitution | 1.3x | ~22% |
| International Affairs | 1.3x | ~21% |
| Economy & Business | 1.1x | ~14% |
| Supreme Court / HC Judgements | 1.1x | Law entrance premium |
| Environment & Science | 1.0x | ~11% |
| Government Schemes | 1.0x | ~9% |
| Awards / Sports / Defence | 0.9x | ~9% |
| Static GK | 0.8x | Declining in CLAT |

### Weakness Boost
Categories where accuracy < 83% get additional 1.2× priority in the daily revision queue.

---

## 6. Revision Dashboard

### Page: `revision_dashboard.html`

### Section 1: Today's Revision Queue
Auto-generated list of sections due for review today:
- Sorted by: overdue priority > weakness boost > category weight
- Each item shows: section title, source PDF, last read date, last test score, days overdue
- "Open to Read" → opens article_viewer at that section
- "Mark as Revised" → records without opening
- After revising all sections → "Take Revision Test" button

### Section 2: Category Health Grid
One card per category showing:
- Current accuracy (from all tests)
- Staleness (days since last revision in this category)
- Sections due for review count
- Color: green (healthy) / yellow (getting stale) / red (urgent)
- Click → shows all sections in that category sorted by urgency

### Section 3: Stale Sections Alert
Sections not reviewed in > 14 days, sorted by:
- Category importance (Polity/International first)
- Original test score (lower = more urgent)
- Age (older = more likely forgotten)

### Section 4: Streak & Progress
- Current revision streak (consecutive days with revision activity)
- Weekly summary: sections revised, tests taken, accuracy trend
- Projected exam readiness: "X% of material revised in last 30 days"

---

## 7. Revision Compilation Page

### Page: `revision_compilation.html`

Dynamically compiled view of ALL sections needing revision:
- Pulls sections with `revision_level >= 3` (Needs Revision or Must Revise)
- Or sections overdue for review (past `next_review_date`)
- Renders them as one scrollable HTML document with:
  - All user highlights and notes preserved
  - Color bars indicating severity
  - "Test This Section" buttons inline
  - "Mark as Revised" buttons
- No file generation — rendered live from database

### Filters
- By category (show only Economy sections)
- By urgency (Must Revise only / Needs Revision + Must Revise)
- By date range (sections from last 2 weeks / last month / all time)

---

## 8. Implementation Phases

### Phase 1: Foundation (Current Session)
- [x] Section-level performance tracking (SID → topic mapping)
- [x] Color-coded viewer overlays (red/purple/blue/green bars)
- [x] Section analysis API endpoint
- [x] Details modal with section breakdown
- [ ] PDF → HTML converter
- [ ] HTML article viewer with highlighting + notes
- [ ] Sample validation with 4 PDFs

### Phase 2: Revision Engine
- [ ] `revision_schedule` table
- [ ] Auto-populate schedule after each test
- [ ] "Mark as Revised" flow (updates schedule)
- [ ] Revision Dashboard page (today's queue + category health)

### Phase 3: Revision Testing
- [ ] "Test This Section" — mini-test from section questions
- [ ] "Revision Test" — test from today's revision queue
- [ ] Post-test SRS interval update
- [ ] Comparison: "First attempt vs re-test" improvement tracking

### Phase 4: Compilation + Deep Revision
- [ ] Revision compilation page (filtered, compiled, annotated)
- [ ] Category deep-dive tests
- [ ] "Re-test PDF" flow
- [ ] Weekly/monthly revision summary reports

---

## 9. Data Flow

```
PDF Upload
  ↓
PDF → HTML Converter (PyMuPDF extract → semantic HTML)
  ↓
Store in html_articles table (one row per section)
  ↓
Also: existing question generation (Claude AI) runs as before
  ↓
Questions linked to sections via SID tags
  ↓
User reads section in HTML viewer
  ↓
User highlights text / adds notes (stored in html_annotations)
  ↓
User takes test (existing assessment flow)
  ↓
Test results update revision_schedule per section
  ↓
Section color bars update in viewer
  ↓
Next day: Revision Dashboard shows sections due for re-reading
  ↓
User re-reads → re-tests → cycle continues
```

---

## 10. Research Basis

### Forgetting Curve (Ebbinghaus, adapted for current affairs)
| Time since learning | Retention without review |
|---|---|
| 24 hours | 30-40% |
| 7 days | 15-20% |
| 30 days | ~10% |

### CLAT GK Pattern (5-year analysis, KollegeApply)
- Polity + International = 43% of all GK questions
- Top 6 categories = 70-75% coverage
- Target: 28+/35 for top-100 rank

### Spaced Repetition Research
- First review must happen within 48 hours (critical window)
- Each successful review roughly doubles the retention interval
- Failed retrieval followed by re-reading produces stronger memory than re-reading alone
- Adaptive intervals (harder items = shorter intervals) reduces workload by 20-30%

### Sources
- NLTI: Score 28+ in CLAT GK strategy
- LegalEdge/TopRankers study plans
- Flames CLAT: Revise like a topper
- KollegeApply: 43% from Polity & IR (5-year breakdown)
- TestFunda: CLAT 2025 GK paper analysis
- Ebbinghaus forgetting curve research
- Roediger & Karpicke 2006: Testing effect
- BCU 2357 spaced repetition method

---

## 11. Current System State (as of 20 April 2026)

### What's already built
- 16,100+ questions across 8 categories, all with MCQ choices
- ~50 test sessions with 1,437 question attempts
- Section-level performance tracking (SID → topic → page mapping)
- Color-coded viewer overlays (live, auto-updates)
- Section analysis API + Details modal breakdown
- Daily GK Summary page (reading time + test scores by day)
- Batch question generator (processed 33 PDFs, ~3,095 questions)
- Test resume flow + beforeunload warning
- PDF upload alternative (when TopRankers CDN blocks)
- Pagination on all tables (25/page)
- Question manager (admin edit/delete answers)
- Unanswered questions page

### Database infrastructure
- `revision_tracker.db`: PDFs, topics, questions, annotations, view sessions, chunks
- `assessment_tracker.db`: test sessions, question attempts, performance, mastery
- `book_practice.db`: RS Aggarwal math practice (separate module)
