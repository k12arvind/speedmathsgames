import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/db';

export async function POST(req: NextRequest) {
  const { sessionId } = await req.json();
  if (!sessionId) return NextResponse.json({ error: 'sessionId required' }, { status: 400 });

  const [responses, session, questions] = await Promise.all([
    prisma.userResponse.findMany({ where: { sessionId }, orderBy: { answeredAt: 'asc' } }),
    prisma.gameSession.findUnique({ where: { id: sessionId } }),
    prisma.questionInstance.findMany({ where: { sessionId }, orderBy: { indexInSession: 'asc' } })
  ]);
  if (!session) return NextResponse.json({ error: 'not found' }, { status: 404 });

  const answeredCount = responses.filter(r=>!r.wasSkipped).length;
  const skippedCount = responses.filter(r=>r.wasSkipped).length;
  const correctCount = responses.filter(r=>r.isCorrect).length;
  const avgTimeMs = Math.round(responses.reduce((s,r)=>s+r.timeTakenMs,0) / Math.max(1,responses.length));
  
  // Calculate composite score: correct answers with time bonus
  const baseScore = correctCount * 100;
  const timeBonus = responses.reduce((bonus, r) => {
    if (r.isCorrect) {
      // Bonus for fast answers (max 50 points per question)
      const timeBonusPoints = Math.max(0, 50 - Math.floor(r.timeTakenMs / 1000));
      return bonus + timeBonusPoints;
    }
    return bonus;
  }, 0);
  const finalScore = baseScore + timeBonus;

  await prisma.gameSession.update({
    where: { id: sessionId },
    data: { 
      endedAt: new Date(), 
      answeredCount, 
      skippedCount, 
      correctCount, 
      avgTimeMs, 
      score: finalScore,
      status: 'completed' 
    }
  });

  const review = questions.map(q => {
    const r = responses.find(x => x.questionId === q.id);
    const ca = (q.payload as any)?.correctAnswer;
    return {
      index: q.indexInSession,
      topic: q.topic,
      prompt: q.prompt,
      userAnswer: r?.userAnswer ?? '',
      correctAnswer: ca?.value ?? null,
      timeTakenMs: r?.timeTakenMs ?? null,
      wasSkipped: r?.wasSkipped ?? false,
      isCorrect: r?.isCorrect ?? false
    };
  });

  // Compute stats by topic
  const byTopic: Record<string, any> = {};
  questions.forEach(q => {
    const topic = q.topic;
    if (!byTopic[topic]) {
      byTopic[topic] = { answered: 0, correct: 0, totalTime: 0 };
    }
    const r = responses.find(x => x.questionId === q.id);
    if (r && !r.wasSkipped) {
      byTopic[topic].answered++;
      if (r.isCorrect) byTopic[topic].correct++;
      byTopic[topic].totalTime += r.timeTakenMs;
    }
  });

  // Generate insights
  const insights = [];
  const accuracy = answeredCount ? correctCount/answeredCount : 0;
  if (accuracy >= 0.9) insights.push("Excellent accuracy! 🎯");
  else if (accuracy >= 0.7) insights.push("Good accuracy, keep practicing! 👍");
  else insights.push("Focus on accuracy - slow down if needed 🎯");

  if (avgTimeMs < 3000) insights.push("Lightning fast responses! ⚡");
  else if (avgTimeMs > 10000) insights.push("Take your time, but try to be a bit quicker ⏱️");

  return NextResponse.json({
    score: finalScore,
    accuracy,
    avgTimeMs,
    correctCount,
    answeredCount,
    byTopic,
    review,
    insights
  });
}
