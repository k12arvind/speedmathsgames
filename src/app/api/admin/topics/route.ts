import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/db';

export async function POST(req: NextRequest) {
  const list = await req.json();
  if (!Array.isArray(list)) return NextResponse.json({ error: 'array expected' }, { status: 400 });
  // Simple upsert by topic
  for (const item of list) {
    if (!item.topic) continue;
    await prisma.topicConfig.upsert({
      where: { id: item.id || '00000000-0000-0000-0000-000000000000' }, // fallback to create
      update: { rules: item.rules ?? {}, validation: item.validation ?? {}, isActive: item.isActive ?? true, version: (item.version ?? 0) + 1 },
      create: { topic: item.topic, rules: item.rules ?? {}, validation: item.validation ?? {}, isActive: item.isActive ?? true },
    });
  }
  return NextResponse.json({ ok: true });
}
