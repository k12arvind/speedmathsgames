import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/db';

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const scope = searchParams.get('scope') || 'daily';
  const topic = searchParams.get('topic') || 'overall';

  try {
    // Get completed sessions from the last period
    let dateFilter = new Date();
    switch (scope) {
      case 'daily':
        dateFilter.setDate(dateFilter.getDate() - 1);
        break;
      case 'weekly':
        dateFilter.setDate(dateFilter.getDate() - 7);
        break;
      case 'alltime':
        dateFilter = new Date('2020-01-01'); // Far back date
        break;
    }

    const sessions = await prisma.gameSession.findMany({
      where: {
        status: 'completed',
        endedAt: { gte: dateFilter }
      },
      include: {
        user: { select: { username: true } }
      },
      orderBy: [
        { correctCount: 'desc' },
        { avgTimeMs: 'asc' }
      ],
      take: 50
    });

    const entries = sessions.map((session, index) => ({
      rank: index + 1,
      username: session.user.username,
      score: session.correctCount,
      accuracy: session.answeredCount > 0 ? Math.round((session.correctCount / session.answeredCount) * 100) : 0,
      avgTimeMs: session.avgTimeMs,
      totalQuestions: session.answeredCount + session.skippedCount
    }));

    return NextResponse.json({ 
      scope, 
      topic, 
      entries, 
      asOf: new Date().toISOString() 
    });
  } catch (error) {
    return NextResponse.json({ error: 'Failed to fetch leaderboard' }, { status: 500 });
  }
}
