import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/db';
import { AnswerSchema } from '@/lib/validators';
import { compareExactIntegers, compareExactDp, compareFractions } from '@/lib/compare';

export async function POST(req: NextRequest) {
  const body = await req.json();
  const parsed = AnswerSchema.safeParse(body);
  if (!parsed.success) return NextResponse.json({ error: parsed.error.format() }, { status: 400 });

  const { sessionId, questionId, userAnswer, timeTakenMs } = parsed.data;

  const qi = await prisma.questionInstance.findUnique({ where: { id: questionId } });
  if (!qi) return NextResponse.json({ error: 'question not found' }, { status: 404 });

  // Extract correct answer from payload
  const payload: any = qi.payload;
  const ca = payload?.correctAnswer;
  let isCorrect = false;

  if (ca?.kind === 'number') {
    const mode = ca.validation || 'exact';
    if (mode === 'exact' && (ca.dp ?? null) === null) {
      isCorrect = compareExactIntegers(userAnswer, ca.value);
    } else if (mode === 'exact' && typeof ca.dp === 'number') {
      isCorrect = compareExactDp(userAnswer, ca.value, ca.dp);
    } else {
      // default fallback
      isCorrect = compareExactIntegers(userAnswer, ca.value);
    }
  } else if (ca?.kind === 'fraction') {
    isCorrect = compareFractions(userAnswer, ca.value, ca.requireLowestTerms ?? true);
  } else {
    // Unknown type - fallback to string comparison
    isCorrect = userAnswer.trim() === ca?.value?.trim();
  }

  await prisma.userResponse.create({
    data: { sessionId, questionId, userAnswer, timeTakenMs, isCorrect, wasSkipped: false }
  });

  return NextResponse.json({ accepted: true, nextIndex: qi.indexInSession + 1 });
}
