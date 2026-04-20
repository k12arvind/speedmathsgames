# Revision Settings — Specification

**Date**: 20 April 2026

---

## Settings Page: `revision_settings.html`

Admin-only page (parent accounts) to configure all revision parameters.
Settings stored in a `revision_settings` table as key-value pairs with JSON values.

---

## Settings Categories

### 1. Daily Workload

| Setting | Key | Type | Default | Range | Description |
|---|---|---|---|---|---|
| New sections per day | `daily_new_sections` | number | 6 | 0-30 | How many sections from unread PDFs to show per day |
| Revision sections per day | `daily_revision_sections` | number | 8 | 0-30 | Max revision sections due per day |
| Total daily cap | `daily_total_cap` | number | 14 | 5-50 | Hard cap — total sections (new + revision) shown per day |
| Estimated time per section (min) | `minutes_per_section` | number | 4 | 1-15 | For time estimate display |

### 2. Revision Buckets

Three configurable time buckets for revision priority:

| Setting | Key | Type | Default | Description |
|---|---|---|---|---|
| **Recent bucket** label | `bucket_recent_label` | text | "Recent (0-30 days)" | |
| Recent bucket range (days) | `bucket_recent_days` | number | 30 | PDFs read within this many days |
| Recent bucket priority | `bucket_recent_priority` | select | High | How aggressively to schedule revision |
| Recent revision interval | `bucket_recent_interval` | number | 7 | Default days between revisions for this bucket |
| **Older bucket** label | `bucket_older_label` | text | "Older (30-90 days)" | |
| Older bucket range (days) | `bucket_older_days` | number | 90 | PDFs read between recent and this many days |
| Older bucket priority | `bucket_older_priority` | select | Medium | |
| Older revision interval | `bucket_older_interval` | number | 14 | |
| **Archive bucket** label | `bucket_archive_label` | text | "Archive (90+ days)" | |
| Archive bucket priority | `bucket_archive_priority` | select | Low | |
| Archive revision interval | `bucket_archive_interval` | number | 30 | |

### 3. "New" PDF Definition

| Setting | Key | Type | Default | Description |
|---|---|---|---|---|
| New PDF window (days) | `new_pdf_window_days` | number | 30 | PDFs created/uploaded within this many days are "new" |
| Prioritize new over revision | `new_over_revision` | boolean | true | When true, new PDFs appear before revision items |
| New-to-revision ratio | `new_revision_ratio` | text | "1:2" | For every 1 new section, show 2 revision sections |

### 4. SRS Intervals

| Setting | Key | Type | Default | Description |
|---|---|---|---|---|
| After 85%+ test | `srs_excellent_multiplier` | number | 2.0 | Multiply current interval by this |
| After 70-84% test | `srs_good_interval` | number | 7 | Fixed interval in days |
| After 50-69% test | `srs_weak_interval` | number | 3 | |
| After <50% test | `srs_poor_interval` | number | 1 | |
| After read, no test | `srs_read_only_interval` | number | 7 | |
| After "Mark as Revised" | `srs_mark_revised_interval` | number | 5 | |
| Mastery threshold (%) | `srs_mastery_threshold` | number | 85 | Accuracy needed for "good" rating |
| Consecutive good for mastery | `srs_mastery_consecutive` | number | 3 | Times scoring above threshold to achieve mastery |
| Max interval (days) | `srs_max_interval` | number | 60 | Cap on how far apart revisions can be |
| Mastered review interval | `srs_mastered_interval` | number | 60 | Interval for mastered sections |

### 5. Category Weights

| Setting | Key | Type | Default | Description |
|---|---|---|---|---|
| Polity & Constitution | `weight_polity` | number | 1.3 | Priority multiplier |
| International Affairs | `weight_international` | number | 1.3 | |
| Supreme Court / HC | `weight_supreme_court` | number | 1.3 | |
| Economy & Business | `weight_economy` | number | 1.2 | |
| Environment & Science | `weight_environment` | number | 1.1 | |
| Awards / Sports / Defence | `weight_awards` | number | 1.0 | |
| Government Schemes | `weight_government` | number | 1.0 | |
| Static GK | `weight_static` | number | 0.8 | |
| Weakness boost threshold (%) | `weakness_boost_threshold` | number | 83 | Categories below this get extra priority |
| Weakness boost multiplier | `weakness_boost_multiplier` | number | 1.2 | Extra multiplier for weak categories |

### 6. Schedule Overrides

| Setting | Key | Type | Default | Description |
|---|---|---|---|---|
| Weekend mode | `weekend_mode` | select | "reduced" | "normal" / "reduced" / "off" |
| Weekend load (%) | `weekend_load_percent` | number | 50 | % of normal daily load on weekends |
| Holiday dates | `holiday_dates` | text[] | [] | Specific dates with reduced/no load |
| Holiday load (%) | `holiday_load_percent` | number | 25 | % of normal load on holidays |
| Exam date | `exam_date` | date | null | CLAT exam date — used for intensity ramp |
| Intensity ramp | `intensity_ramp` | boolean | true | Increase daily load as exam approaches |
| Ramp start (days before exam) | `ramp_start_days` | number | 60 | When to start increasing load |
| Ramp multiplier at exam | `ramp_peak_multiplier` | number | 1.5 | Max load multiplier near exam |

### 7. Display Preferences

| Setting | Key | Type | Default | Description |
|---|---|---|---|---|
| Show mastered sections | `show_mastered` | boolean | false | Show mastered sections on dashboard |
| Group by category | `group_by_category` | boolean | false | Group revision queue by category vs by urgency |
| Show time estimates | `show_time_estimates` | boolean | true | Show "~38 min estimated" on dashboard |
| Default test question count | `revision_test_count` | number | 20 | Max questions in a revision test |

---

## Database

```sql
CREATE TABLE revision_settings (
    setting_key TEXT PRIMARY KEY,
    setting_value TEXT NOT NULL,  -- JSON-encoded value
    setting_type TEXT NOT NULL,   -- 'number', 'boolean', 'text', 'select', 'date', 'text[]'
    category TEXT NOT NULL,       -- 'workload', 'buckets', 'srs', 'weights', 'schedule', 'display'
    label TEXT NOT NULL,          -- Human-readable label
    description TEXT,             -- Help text
    min_value REAL,               -- For number types
    max_value REAL,               -- For number types
    options TEXT,                 -- JSON array of options for 'select' type
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Settings Page Layout

```
┌─────────────────────────────────────────────────────────────┐
│  Revision Settings                    [Save All] [Reset]    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  [Daily Workload] [Buckets] [SRS] [Weights] [Schedule] [UI]│
│                                                             │
│  ═══ Daily Workload ═══                                     │
│                                                             │
│  New sections per day          [====●====] 6                │
│  How many sections from unread PDFs per day                 │
│                                                             │
│  Revision sections per day     [======●==] 8                │
│  Max revision sections due per day                          │
│                                                             │
│  Total daily cap               [=======●=] 14               │
│  Hard cap — total shown per day                             │
│                                                             │
│  ═══ Revision Buckets ═══                                   │
│                                                             │
│  Recent (0-30 days)                                         │
│  ┌──────────────────────────────────────────────┐           │
│  │  Range: [30] days   Priority: [High ▾]       │           │
│  │  Default interval: [7] days                  │           │
│  └──────────────────────────────────────────────┘           │
│                                                             │
│  Older (30-90 days)                                         │
│  ┌──────────────────────────────────────────────┐           │
│  │  Range: [90] days   Priority: [Medium ▾]     │           │
│  │  Default interval: [14] days                 │           │
│  └──────────────────────────────────────────────┘           │
│                                                             │
│  Archive (90+ days)                                         │
│  ┌──────────────────────────────────────────────┐           │
│  │  Priority: [Low ▾]                           │           │
│  │  Default interval: [30] days                 │           │
│  └──────────────────────────────────────────────┘           │
│                                                             │
│  ═══ Schedule ═══                                           │
│                                                             │
│  CLAT Exam Date:  [2026-12-08]                              │
│  Weekend mode:    [Reduced ▾]  Load: [50]%                  │
│  Holidays:        [+ Add date]                              │
│    • 15 Aug 2026 (Independence Day)   [×]                   │
│    • 2 Oct 2026 (Gandhi Jayanti)      [×]                   │
│                                                             │
│  Intensity ramp: [✓] Start [60] days before exam            │
│  Peak multiplier: [1.5x]                                    │
│                                                             │
│                                [Save All Changes]           │
└─────────────────────────────────────────────────────────────┘
```

---

## API Endpoints

```
GET  /api/revision/settings           — get all settings
POST /api/revision/settings           — save settings (bulk update)
GET  /api/revision/settings/{key}     — get single setting
POST /api/revision/settings/reset     — reset all to defaults
```

---

## How Settings Flow Into the Revision Engine

```
Daily Revision Queue Generation:

1. Load settings from revision_settings table
2. Determine today's context:
   - Is it weekend? → apply weekend_load_percent
   - Is it holiday? → apply holiday_load_percent
   - Days until exam → apply intensity ramp multiplier
3. Calculate today's capacity:
   - base = daily_total_cap
   - adjusted = base × weekend/holiday factor × ramp factor
4. Split capacity: new vs revision (based on new_revision_ratio)
5. Fill revision slots:
   - Query revision_schedule WHERE next_review_date <= today
   - Sort by: revision_level DESC, category_weight DESC
   - Apply bucket priorities (recent > older > archive)
   - Take top N up to revision slot count
6. Fill new slots:
   - Query unread PDFs within new_pdf_window_days
   - Pick sections from highest-weighted categories first
   - Take top N up to new slot count
7. Return combined queue
```
