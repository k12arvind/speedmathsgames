import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/db';
import { generateQuestion } from '@/lib/questionGenerators';

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const sessionId = searchParams.get('sessionId');
  const index = Number(searchParams.get('index') || '0');
  if (!sessionId) return NextResponse.json({ error: 'sessionId required' }, { status: 400 });

  const session = await prisma.gameSession.findUnique({ where: { id: sessionId } });
  if (!session) return NextResponse.json({ error: 'not found' }, { status: 404 });

  // Resolve topic list & configs (simplified: pull TopicConfig by topic names; fallback to defaults)
  const requestedTopics: string[] = (session.config as any)?.topics?.map((t:any)=> t.name || t) ?? ['addition','decimals'];
  const topic = requestedTopics[index % requestedTopics.length];

  // Load TopicConfig if exists
  const topicCfg = await prisma.topicConfig.findFirst({ where: { topic, isActive: true } });

  const seed = Number((session.config as any)?.seed || 1);
  const gq = generateQuestion(topic, topicCfg, seed, index);

  const qi = await prisma.questionInstance.create({
    data: {
      sessionId,
      indexInSession: index,
      topic: gq.topic,
      difficulty: gq.difficulty,
      prompt: gq.prompt,
      payload: gq.payload
    }
  });

  return NextResponse.json({
    question: {
      id: qi.id,
      indexInSession: qi.indexInSession,
      topic: qi.topic,
      difficulty: qi.difficulty,
      prompt: qi.prompt,
      inputType: 'number'
    }
  });
}
