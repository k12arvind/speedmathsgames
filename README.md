# SpeedMathsGames

A fast-paced math quiz game built with Next.js, TypeScript, and PostgreSQL. Test your mental math skills across various topics including addition, multiplication, fractions, decimals, and BODMAS order of operations.

🚀 **Live at: [speedmathsgames.com](https://speedmathsgames.com)**

## Features

- **Multiple Math Topics**: Addition, multiplication, fractions, decimals, BODMAS
- **Adaptive Difficulty**: Easy, medium, and hard levels for each topic
- **Real-time Gameplay**: Timed questions with instant feedback
- **Smart Scoring**: Points for correct answers plus time bonuses
- **Leaderboards**: Daily, weekly, and all-time rankings
- **Admin Dashboard**: Configure topics and question rules
- **Responsive Design**: Works on desktop and mobile

## Quick Start

### Prerequisites
- Node.js 18+ 
- PostgreSQL database
- npm or yarn

### Installation

```bash
# Clone and install
git clone <your-repo-url>
cd speedmathsgames
npm install

# Setup environment
cp .env.example .env
# Edit .env with your PostgreSQL connection string

# Setup database
npm run db:migrate    # Production: creates migration
# OR
npm run db:push      # Development: fast schema sync

# Start development server
npm run dev
```

Visit [http://localhost:3000](http://localhost:3000) to play!

## Architecture

### Game Flow
1. **Authentication**: Simple username-based guest accounts
2. **Game Setup**: Choose topics, difficulty, and time limit  
3. **Live Gameplay**: Answer questions as fast as possible
4. **Results**: See score, accuracy, and topic-specific insights

### Tech Stack
- **Frontend**: Next.js 14, React, TypeScript
- **Backend**: Next.js API Routes
- **Database**: PostgreSQL with Prisma ORM
- **Deployment**: Vercel-ready

### Question Generation
- **Seeded RNG**: Deterministic questions using Mulberry32 algorithm
- **Topic Modules**: Modular generators for each math topic
- **Configurable Rules**: Admin can adjust difficulty and constraints

## Development

### Available Scripts
```bash
npm run dev          # Start development server
npm run build        # Build for production
npm run start        # Start production server
npm run lint         # Run ESLint
npm run db:push      # Push schema changes (dev)
npm run db:migrate   # Create migration (prod)
```

### Adding New Math Topics
1. Create generator in `src/lib/questionGenerators/[topic].ts`
2. Add to switch statement in `src/lib/questionGenerators/index.ts`
3. Update topic list in `src/lib/validators.ts`
4. Add topic configuration via admin interface

## Deployment

### Environment Variables
```env
DATABASE_URL="postgresql://user:pass@host:5432/dbname"
NEXTAUTH_URL="https://your-domain.com"
NEXTAUTH_SECRET="your-secret-key"
```

### Deploy to Vercel
```bash
# Connect to Vercel
npx vercel

# Set up PostgreSQL database (recommend Railway/Supabase/Neon)
# Configure environment variables in Vercel dashboard
# Deploy!
```

## License

MIT License - feel free to use this for your own math game projects!
