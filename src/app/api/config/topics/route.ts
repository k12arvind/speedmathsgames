import { NextResponse } from 'next/server';
import { prisma } from '@/lib/db';

export async function GET() {
  const topics = await prisma.topicConfig.findMany({ where: { isActive: true } });
  return NextResponse.json(topics);
}
