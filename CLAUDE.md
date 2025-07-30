# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

```bash
# Setup
npm install
cp .env.example .env
# Set DATABASE_URL in .env to point to PostgreSQL

# Database
npm run db:push           # Fast schema push to DB (development)
npm run db:migrate        # Create migration named 'init' (production-ready)

# Development
npm run dev               # Start development server at http://localhost:3000
npm run build             # Build for production
npm run start             # Start production server
npm run lint              # Run ESLint
```

## Architecture Overview

SpeedMathsGames is a Next.js 14 app with PostgreSQL/Prisma for a timed math quiz platform.

### Core Game Flow
1. **Authentication**: Username-only guest auth via `/api/auth/guest` (OAuth scaffolded but disabled)
2. **Game Setup**: User selects topics/difficulty, creates GameSession via `/api/game/start`
3. **Question Generation**: Seeded RNG generates questions dynamically via `src/lib/questionGenerators/`
4. **Gameplay**: Real-time question-answer loop through `/api/game/next`, `/api/game/answer`, `/api/game/skip`
5. **Results**: Session ends via `/api/game/finish`, tracks stats and leaderboards

### Key Data Models (Prisma)
- **User**: Basic user info, linked to sessions
- **GameSession**: Core game state, config, timing, scoring
- **QuestionInstance/UserResponse**: Question-answer pairs with timing data
- **TopicConfig/GamePreset**: Admin-configurable game rules and presets
- **UserTopicStats/Leaderboard**: Performance tracking and rankings

### Question Generation System
Located in `src/lib/questionGenerators/`:
- **Seeded RNG**: Deterministic question generation using `mulberry32` algorithm
- **Topic Modules**: `addition.ts`, `decimals.ts`, `multiplication.ts`, `fractions.ts`, `bodmas.ts`
- **Central Dispatcher**: `index.ts` routes to appropriate generator based on topic
- **Validation**: Answer comparison logic in `src/lib/compare.ts`

### Admin System
- **Location**: `/admin` routes for topic/preset management
- **Features**: JSON editors for `TopicConfig.rules` and `GamePreset.config`
- **API**: `/api/admin/topics` and `/api/admin/presets` for CRUD operations

### Authentication Pattern
- Guest-only MVP: Users create accounts with username only
- Session stored in `smg_user` cookie
- Google OAuth placeholders exist but disabled
- No password/email validation in current implementation

### Database Connection
- **File**: `src/lib/db.ts`
- **Pattern**: Global Prisma client with hot-reload protection
- **Schema**: PostgreSQL with UUID primary keys, JSON config storage

## Key Files to Understand
- `prisma/schema.prisma`: All data models and relationships
- `src/lib/questionGenerators/index.ts`: Question generation entry point
- `src/app/api/game/start/route.ts`: Game session creation logic
- `src/lib/validators.ts`: Zod schemas for API validation
- `src/lib/scoring.ts`: Score calculation algorithms