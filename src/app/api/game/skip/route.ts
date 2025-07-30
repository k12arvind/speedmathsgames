import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/db';
import { SkipSchema } from '@/lib/validators';

export async function POST(req: NextRequest) {
  const body = await req.json();
  const parsed = SkipSchema.safeParse(body);
  if (!parsed.success) return NextResponse.json({ error: parsed.error.format() }, { status: 400 });

  const { sessionId, questionId, timeTakenMs } = parsed.data;
  await prisma.userResponse.create({
    data: { sessionId, questionId, userAnswer: '', timeTakenMs, isCorrect: false, wasSkipped: true }
  });
  return NextResponse.json({ accepted: true, nextIndex: null });
}
