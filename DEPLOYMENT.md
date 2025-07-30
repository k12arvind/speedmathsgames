# Deployment Guide for SpeedMathsGames.com

This guide will help you deploy the SpeedMathsGames application to production.

## Prerequisites

- GitHub account (for code hosting)
- Vercel account (for hosting)
- PostgreSQL database (Railway, Supabase, or Neon recommended)
- Domain name `speedmathsgames.com` (if desired)

## Step-by-Step Deployment

### 1. Push to GitHub

```bash
# Create a new repository on GitHub first, then:
git remote add origin https://github.com/yourusername/speedmathsgames.git
git branch -M main
git push -u origin main
```

### 2. Set up PostgreSQL Database

**Option A: Railway (Recommended)**
1. Go to [railway.app](https://railway.app)
2. Create new project → "PostgreSQL"
3. Copy the connection string from the "Variables" tab

**Option B: Supabase**
1. Go to [supabase.com](https://supabase.com)
2. Create new project
3. Go to Settings → Database → Connection String
4. Use the "URI" format connection string

**Option C: Neon**
1. Go to [neon.tech](https://neon.tech)
2. Create new project
3. Copy the connection string from the dashboard

### 3. Deploy to Vercel

1. Go to [vercel.com](https://vercel.com) and sign in
2. Click "New Project"
3. Import your GitHub repository
4. Configure environment variables:
   - `DATABASE_URL`: Your PostgreSQL connection string
   - `NEXTAUTH_URL`: `https://your-domain.com` (or use Vercel domain)
   - `NEXTAUTH_SECRET`: Generate with `openssl rand -base64 32`

### 4. Run Database Migration

After deployment, you need to set up the database schema:

```bash
# Install Vercel CLI if you haven't
npm i -g vercel

# Login to Vercel
vercel login

# Run migration on production
vercel env pull .env.local
npx prisma migrate deploy
npx prisma generate
```

Alternatively, use the Prisma Studio or run migrations through Vercel's dashboard.

### 5. Custom Domain Setup (Optional)

If you own `speedmathsgames.com`:

1. In Vercel project settings, go to "Domains"
2. Add `speedmathsgames.com` and `www.speedmathsgames.com`
3. Update your domain's DNS settings to point to Vercel:
   - Add CNAME record: `www` → `cname.vercel-dns.com`
   - Add A record: `@` → `76.76.19.61`
4. Wait for DNS propagation (5-60 minutes)

### 6. Environment Variables Reference

Make sure these are set in Vercel:

```env
DATABASE_URL="postgresql://user:pass@host:5432/dbname"
NEXTAUTH_URL="https://speedmathsgames.com"
NEXTAUTH_SECRET="your-generated-secret"
```

### 7. Post-Deployment Testing

1. Visit your deployed site
2. Test user registration: Enter a username on homepage
3. Test game flow: Setup → Play → Review
4. Test admin interface: `/admin` → Topic Configs
5. Test leaderboard: Should populate after games are played

### 8. Optional Enhancements

**Analytics (Google Analytics)**
```bash
npm install @next/third-parties
```
Add GA4 tracking ID to environment variables.

**Error Monitoring (Sentry)**
```bash
npm install @sentry/nextjs
```
Add Sentry DSN to environment variables.

**Performance Monitoring**
Use Vercel's built-in analytics or add custom monitoring.

## Troubleshooting

**Database Connection Issues**
- Verify DATABASE_URL format: `postgresql://user:pass@host:port/db?options`
- Check if database allows external connections
- Ensure SSL mode is correct (most cloud DBs require SSL)

**Build Failures**
- Check Vercel build logs
- Ensure all dependencies are in package.json
- Verify TypeScript types are correct

**Runtime Errors**
- Check Vercel function logs
- Verify environment variables are set
- Test database queries work with your connection

## Success! 🎉

Your SpeedMathsGames application should now be live and accessible. Users can:

- Create accounts and play math quizzes
- Compete on leaderboards
- View detailed game reviews
- Admin can configure topics and difficulty

The app is production-ready with proper error handling, validation, and responsive design.