import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/db';

export async function POST(req: NextRequest) {
  const list = await req.json();
  if (!Array.isArray(list)) return NextResponse.json({ error: 'array expected' }, { status: 400 });
  for (const p of list) {
    if (!p.name) continue;
    await prisma.gamePreset.upsert({
      where: { name: p.name },
      update: { description: p.description ?? null, config: p.config ?? {} },
      create: { name: p.name, description: p.description ?? null, config: p.config ?? {}, createdBy: p.createdBy ?? 'admin' },
    });
  }
  return NextResponse.json({ ok: true });
}
