# Personal Finance & Workout Modules - Implementation Plan

## Overview

Two private modules for Arvind & Deepa only:
1. **Personal Finance Module** - Bank accounts, assets, stocks (MStock API), liabilities
2. **Personal Workout Module** - Workouts, diet, weight, blood reports (OCR extraction)

---

## 🔐 Access Control

### Authorized Users Only
| User | Email | Role | Access |
|------|-------|------|--------|
| Arvind | k12arvind@gmail.com | admin | Full access |
| Deepa | deepay2019@gmail.com | parent | Full access |
| Saanvi | 20saanvi12@gmail.com | child | **NO ACCESS** |
| Navya | 20navya12@gmail.com | child | **NO ACCESS** |

### Implementation
- Add `can_access_private_modules` permission in `user_roles.py`
- API endpoints return 403 for unauthorized users
- Navigation menu hides these modules for children

---

## 💰 Personal Finance Module

### Database Schema: `finance_tracker.db`

```sql
-- Bank Accounts
CREATE TABLE bank_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_name TEXT NOT NULL,           -- "HDFC Savings", "SBI FD"
    bank_name TEXT NOT NULL,
    account_type TEXT NOT NULL,           -- savings, current, fd, rd
    account_number TEXT,                  -- Last 4 digits for reference
    current_balance REAL DEFAULT 0,
    interest_rate REAL,                   -- For FD/RD
    maturity_date TEXT,                   -- For FD/RD (ISO format)
    owner TEXT NOT NULL,                  -- 'arvind', 'deepa', 'joint'
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Balance History (for tracking over time)
CREATE TABLE balance_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    balance REAL NOT NULL,
    recorded_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES bank_accounts(id)
);

-- Assets (Real Estate, Gold, etc.)
CREATE TABLE assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_type TEXT NOT NULL,             -- real_estate, gold, silver, ppf, epf, nps, mutual_fund, other
    name TEXT NOT NULL,                   -- "Flat in Bangalore", "Gold Chain"
    purchase_date TEXT,
    purchase_price REAL,
    current_value REAL,
    quantity REAL,                        -- For gold/silver (grams), MF (units)
    location TEXT,                        -- For real estate
    details TEXT,                         -- JSON for type-specific fields
    owner TEXT NOT NULL,                  -- 'arvind', 'deepa', 'joint'
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Asset Value History
CREATE TABLE asset_value_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL,
    value REAL NOT NULL,
    recorded_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (asset_id) REFERENCES assets(id)
);

-- Stock Holdings (Manual + MStock synced)
CREATE TABLE stock_holdings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,                 -- NSE symbol: "RELIANCE", "TCS"
    exchange TEXT DEFAULT 'NSE',          -- NSE, BSE
    company_name TEXT,
    quantity INTEGER NOT NULL,
    avg_buy_price REAL NOT NULL,
    current_price REAL,
    current_value REAL,                   -- quantity * current_price
    profit_loss REAL,
    profit_loss_percent REAL,
    source TEXT DEFAULT 'manual',         -- 'manual', 'mstock'
    mstock_isin TEXT,                     -- ISIN from MStock for syncing
    owner TEXT NOT NULL,
    last_price_update TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, exchange, owner)
);

-- Stock Watchlist & Research
CREATE TABLE stock_watchlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    exchange TEXT DEFAULT 'NSE',
    company_name TEXT,
    current_price REAL,
    target_price REAL,
    stop_loss REAL,
    research_notes TEXT,                  -- Markdown notes
    rating TEXT,                          -- buy, hold, sell, watch
    added_by TEXT NOT NULL,               -- 'arvind', 'deepa'
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Dividend Records
CREATE TABLE dividends (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    company_name TEXT,
    dividend_amount REAL NOT NULL,
    ex_date TEXT,
    record_date TEXT,
    payment_date TEXT,
    shares_held INTEGER,
    total_received REAL,
    owner TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Liabilities
CREATE TABLE liabilities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    liability_type TEXT NOT NULL,         -- home_loan, car_loan, personal_loan, credit_card, other
    name TEXT NOT NULL,                   -- "HDFC Home Loan", "Axis Credit Card"
    lender TEXT,
    principal_amount REAL,
    interest_rate REAL,
    emi_amount REAL,
    tenure_months INTEGER,
    start_date TEXT,
    end_date TEXT,
    outstanding_balance REAL,
    owner TEXT NOT NULL,
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Liability Payment History
CREATE TABLE liability_payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    liability_id INTEGER NOT NULL,
    payment_date TEXT NOT NULL,
    amount REAL NOT NULL,
    principal_paid REAL,
    interest_paid REAL,
    balance_after REAL,
    notes TEXT,
    FOREIGN KEY (liability_id) REFERENCES liabilities(id)
);

-- Net Worth Snapshots (monthly)
CREATE TABLE net_worth_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_date TEXT NOT NULL,          -- First of month
    total_bank_balance REAL,
    total_assets REAL,
    total_stocks REAL,
    total_liabilities REAL,
    net_worth REAL,
    breakdown TEXT,                       -- JSON with detailed breakdown
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- MStock API Configuration
CREATE TABLE mstock_config (
    id INTEGER PRIMARY KEY DEFAULT 1,
    api_key TEXT,
    client_id TEXT,
    access_token TEXT,
    token_expiry TEXT,
    last_sync TEXT,
    auto_sync_enabled INTEGER DEFAULT 1,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

### API Endpoints: `/api/finance/*`

```
# Bank Accounts
GET    /api/finance/accounts                    - List all accounts
POST   /api/finance/accounts                    - Add new account
PUT    /api/finance/accounts/<id>               - Update account
DELETE /api/finance/accounts/<id>               - Delete account
POST   /api/finance/accounts/<id>/update-balance - Update balance (creates history)

# Assets
GET    /api/finance/assets                      - List all assets
GET    /api/finance/assets/<type>               - Filter by type
POST   /api/finance/assets                      - Add new asset
PUT    /api/finance/assets/<id>                 - Update asset
DELETE /api/finance/assets/<id>                 - Delete asset
POST   /api/finance/assets/<id>/update-value    - Update value (creates history)

# Stocks
GET    /api/finance/stocks                      - List holdings
POST   /api/finance/stocks                      - Add holding
PUT    /api/finance/stocks/<id>                 - Update holding
DELETE /api/finance/stocks/<id>                 - Delete holding
POST   /api/finance/stocks/refresh-prices       - Refresh all prices from MStock
GET    /api/finance/stocks/watchlist            - Get watchlist
POST   /api/finance/stocks/watchlist            - Add to watchlist
PUT    /api/finance/stocks/watchlist/<id>       - Update watchlist item
DELETE /api/finance/stocks/watchlist/<id>       - Remove from watchlist
GET    /api/finance/stocks/quote/<symbol>       - Get live quote from MStock

# Dividends
GET    /api/finance/dividends                   - List dividends
POST   /api/finance/dividends                   - Add dividend

# Liabilities
GET    /api/finance/liabilities                 - List liabilities
POST   /api/finance/liabilities                 - Add liability
PUT    /api/finance/liabilities/<id>            - Update liability
DELETE /api/finance/liabilities/<id>            - Delete liability
POST   /api/finance/liabilities/<id>/payment    - Record payment

# Dashboard & Analytics
GET    /api/finance/dashboard                   - Net worth summary
GET    /api/finance/net-worth-history           - Historical net worth
POST   /api/finance/net-worth-snapshot          - Take snapshot

# MStock Integration
GET    /api/finance/mstock/config               - Get MStock config status
POST   /api/finance/mstock/config               - Save API credentials
POST   /api/finance/mstock/login                - Login to MStock (get token)
POST   /api/finance/mstock/sync                 - Sync portfolio from MStock
GET    /api/finance/mstock/positions            - Get live positions from MStock
```

### MStock API Integration

**API Documentation:** https://tradingapi.mstock.com/docs/v1/Introduction/

**Authentication Flow:**
1. Register app and get `api_key` and `client_id`
2. User logs in via MStock login page (OAuth-like)
3. Get `access_token` (valid till midnight IST)
4. Store token in `mstock_config` table
5. Daily re-authentication required

**Key Endpoints We'll Use:**
- `GET /holdings` - Get portfolio holdings
- `GET /positions` - Get intraday positions
- `GET /quotes` - Get live stock quotes
- `GET /historical-candles` - Get historical data

**Rate Limits:**
- Order APIs: 30/second
- Data APIs: 1/second  
- Quote APIs: 20/second

### Frontend Pages

```
dashboard/
├── finance_dashboard.html      - Net worth overview, allocation charts
├── finance_accounts.html       - Bank accounts management
├── finance_assets.html         - Assets tracking (real estate, gold, etc.)
├── finance_stocks.html         - Stock portfolio & watchlist
├── finance_liabilities.html    - Loans & liabilities
└── finance_mstock.html         - MStock API configuration
```

---

## 🏋️ Personal Workout Module

### Database Schema: `health_tracker.db`

```sql
-- User Profiles (weight goals, etc.)
CREATE TABLE health_profiles (
    user_id TEXT PRIMARY KEY,             -- 'arvind', 'deepa'
    current_weight REAL,
    target_weight REAL,
    height_cm REAL,
    date_of_birth TEXT,
    blood_group TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Weight Log
CREATE TABLE weight_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    weight REAL NOT NULL,
    body_fat_percent REAL,                -- Optional
    muscle_mass REAL,                     -- Optional
    notes TEXT,
    recorded_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Workouts
CREATE TABLE workouts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    workout_date TEXT NOT NULL,
    workout_type TEXT NOT NULL,           -- gym, cardio, yoga
    duration_minutes INTEGER,
    intensity TEXT,                       -- light, moderate, intense
    exercises TEXT,                       -- JSON array of exercises
    calories_burned INTEGER,              -- Optional estimate
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Exercise Library (for gym workouts)
CREATE TABLE exercise_library (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT,                        -- chest, back, legs, shoulders, arms, core, cardio
    equipment TEXT,                       -- barbell, dumbbell, machine, bodyweight
    description TEXT,
    is_custom INTEGER DEFAULT 0
);

-- Workout Templates (pre-defined routines)
CREATE TABLE workout_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,                   -- "Push Day", "Leg Day"
    workout_type TEXT,
    exercises TEXT,                       -- JSON array
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Diet Log
CREATE TABLE diet_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    log_date TEXT NOT NULL,
    meal_type TEXT,                       -- breakfast, lunch, dinner, snack
    meal_notes TEXT,                      -- Simple description
    water_glasses INTEGER,                -- Water intake
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Blood Reports
CREATE TABLE blood_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    report_date TEXT NOT NULL,
    lab_name TEXT,
    report_type TEXT,                     -- full_body, lipid, thyroid, diabetes, etc.
    pdf_path TEXT,                        -- Path to stored PDF
    pdf_filename TEXT,
    extracted_data TEXT,                  -- JSON with OCR-extracted values
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Blood Test Parameters (extracted values over time)
CREATE TABLE blood_parameters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id INTEGER NOT NULL,
    user_id TEXT NOT NULL,
    parameter_name TEXT NOT NULL,         -- "Hemoglobin", "Cholesterol Total"
    parameter_category TEXT,              -- hematology, lipid, liver, kidney, thyroid, diabetes
    value REAL,
    unit TEXT,
    reference_min REAL,
    reference_max REAL,
    is_abnormal INTEGER DEFAULT 0,
    recorded_date TEXT NOT NULL,
    FOREIGN KEY (report_id) REFERENCES blood_reports(id)
);

-- Common Blood Parameters Reference
CREATE TABLE parameter_reference (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parameter_name TEXT NOT NULL UNIQUE,
    category TEXT,
    unit TEXT,
    reference_min_male REAL,
    reference_max_male REAL,
    reference_min_female REAL,
    reference_max_female REAL,
    description TEXT
);

-- Health Goals
CREATE TABLE health_goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    goal_type TEXT,                       -- weight_loss, muscle_gain, run_5k, etc.
    target_value REAL,
    target_date TEXT,
    current_value REAL,
    status TEXT DEFAULT 'active',         -- active, completed, abandoned
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

### Blood Report OCR Strategy

**Approach:** Use Python libraries for PDF text extraction + Claude AI for intelligent parsing

1. **PDF Text Extraction:**
   - `PyMuPDF (fitz)` - Already installed, handles most PDFs
   - `pdfplumber` - Better for table extraction
   - `pdf2image` + `pytesseract` - For scanned PDFs (OCR fallback)

2. **AI-Powered Parsing:**
   - Extract raw text from PDF
   - Send to Claude with prompt to identify health parameters
   - Claude returns structured JSON with parameter names, values, units

3. **Parameter Mapping:**
   - Map extracted parameters to standard names
   - Store in `blood_parameters` table
   - Track trends over time

### API Endpoints: `/api/health/*`

```
# Profile
GET    /api/health/profile                      - Get user profile
PUT    /api/health/profile                      - Update profile

# Weight
GET    /api/health/weight                       - Weight history
POST   /api/health/weight                       - Log weight
DELETE /api/health/weight/<id>                  - Delete entry

# Workouts
GET    /api/health/workouts                     - List workouts (with filters)
GET    /api/health/workouts/<id>                - Get workout details
POST   /api/health/workouts                     - Log workout
PUT    /api/health/workouts/<id>                - Update workout
DELETE /api/health/workouts/<id>                - Delete workout
GET    /api/health/workouts/templates           - Get templates
POST   /api/health/workouts/templates           - Save template

# Diet
GET    /api/health/diet                         - Diet log (date range)
POST   /api/health/diet                         - Log meal
PUT    /api/health/diet/<id>                    - Update meal
DELETE /api/health/diet/<id>                    - Delete meal

# Blood Reports
GET    /api/health/reports                      - List reports
GET    /api/health/reports/<id>                 - Get report with parameters
POST   /api/health/reports/upload               - Upload PDF & extract
DELETE /api/health/reports/<id>                 - Delete report
GET    /api/health/parameters                   - Get parameter trends
GET    /api/health/parameters/<name>            - Get specific parameter history

# Dashboard
GET    /api/health/dashboard                    - Overview stats
GET    /api/health/dashboard/<user_id>          - Specific user (both can view each other)

# Goals
GET    /api/health/goals                        - List goals
POST   /api/health/goals                        - Add goal
PUT    /api/health/goals/<id>                   - Update goal
```

### Frontend Pages

```
dashboard/
├── health_dashboard.html       - Overview for both users
├── health_workout.html         - Log & view workouts
├── health_diet.html            - Diet logging
├── health_weight.html          - Weight tracking with chart
├── health_reports.html         - Blood reports & parameter trends
└── health_goals.html           - Goals tracking
```

---

## 📁 File Structure

```
~/clat_preparation/
├── server/
│   ├── finance_db.py           # Finance database operations
│   ├── finance_api.py          # Finance API handlers  
│   ├── mstock_client.py        # MStock API wrapper
│   ├── health_db.py            # Health database operations
│   ├── health_api.py           # Health API handlers
│   ├── blood_report_parser.py  # PDF parsing & OCR
│   └── user_roles.py           # Updated with private module access
├── dashboard/
│   ├── finance_dashboard.html
│   ├── finance_accounts.html
│   ├── finance_assets.html
│   ├── finance_stocks.html
│   ├── finance_liabilities.html
│   ├── finance_mstock.html
│   ├── health_dashboard.html
│   ├── health_workout.html
│   ├── health_diet.html
│   ├── health_weight.html
│   ├── health_reports.html
│   └── health_goals.html
├── finance_tracker.db          # Finance database
├── health_tracker.db           # Health database
└── health_reports/             # Stored blood report PDFs
    ├── arvind/
    └── deepa/
```

---

## 📱 Mobile Optimization

All pages will be mobile-first with:
- Responsive Bootstrap 5 layout
- Touch-friendly buttons and inputs
- Swipe gestures for common actions
- Bottom navigation for quick access
- PWA-ready (can add to home screen)

---

## 🎨 UI/UX Design

### Finance Module Theme
- **Primary Color:** Deep blue (#1a365d) - Trust, stability
- **Accent:** Green for gains, Red for losses
- **Charts:** Pie charts for allocation, Line charts for trends
- **Cards:** Clean, modern cards for each section

### Health Module Theme  
- **Primary Color:** Teal (#0d9488) - Health, vitality
- **Accent:** Purple for achievements
- **Charts:** Weight trend lines, Progress rings for goals
- **Cards:** Activity cards with icons

---

## 🔧 Implementation Phases

### Phase 1: Foundation (Week 1)
- [ ] Update `user_roles.py` with private module permissions
- [ ] Create `finance_db.py` with database schema
- [ ] Create `health_db.py` with database schema
- [ ] Basic API endpoint structure in `unified_server.py`

### Phase 2: Finance Core (Week 2)
- [ ] Bank accounts CRUD
- [ ] Assets tracking CRUD
- [ ] Liabilities tracking CRUD
- [ ] Finance dashboard with net worth
- [ ] Basic frontend pages

### Phase 3: Stock Integration (Week 3)
- [ ] Manual stock holdings
- [ ] MStock API client
- [ ] MStock authentication flow
- [ ] Portfolio sync from MStock
- [ ] Live price refresh
- [ ] Stock watchlist

### Phase 4: Health Core (Week 4)
- [ ] Weight logging with charts
- [ ] Workout logging
- [ ] Diet notes
- [ ] Basic health dashboard
- [ ] Frontend pages

### Phase 5: Blood Reports (Week 5)
- [ ] PDF upload & storage
- [ ] Text extraction from PDFs
- [ ] Claude AI parameter parsing
- [ ] Parameter trend tracking
- [ ] Report history view

### Phase 6: Polish (Week 6)
- [ ] Mobile optimization
- [ ] Charts and visualizations
- [ ] Goals tracking
- [ ] Data export features
- [ ] Testing & bug fixes

---

## 🔒 Security Considerations

1. **API Key Storage:** MStock API keys stored encrypted
2. **File Uploads:** Blood reports validated (PDF only, size limits)
3. **Access Control:** Every endpoint checks `is_parent()` 
4. **Data Isolation:** Finance/health data completely separate from kids' data
5. **No External Exposure:** These endpoints not exposed to public

---

## 📊 Sample MStock API Import

When user provides MStock export, expected fields:
- Symbol/ISIN
- Quantity
- Average Cost
- Current Market Price
- P&L
- Day's P&L

I'll design import to handle CSV/Excel exports from MStock.

---

## 🩺 Sample Blood Report Parameters

Common parameters to track:
```
HEMATOLOGY:
- Hemoglobin
- WBC Count
- RBC Count
- Platelet Count

DIABETES:
- Fasting Blood Sugar
- HbA1c
- Post Prandial Blood Sugar

LIPID PROFILE:
- Total Cholesterol
- HDL Cholesterol
- LDL Cholesterol
- Triglycerides
- VLDL

LIVER FUNCTION:
- SGOT (AST)
- SGPT (ALT)
- Bilirubin
- Alkaline Phosphatase

KIDNEY FUNCTION:
- Creatinine
- BUN/Urea
- Uric Acid
- eGFR

THYROID:
- TSH
- T3
- T4

VITAMINS:
- Vitamin D
- Vitamin B12
- Iron/Ferritin
```

---

## Next Steps

1. **You provide:** MStock CSV/Excel export sample
2. **You provide:** Sample blood test report PDF
3. **I'll start:** Building the database schemas and APIs in parallel
4. **MStock Setup:** You'll need to register for Trading API at https://tradingapi.mstock.com/

Ready to begin implementation? 🚀

