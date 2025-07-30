import { NextResponse } from 'next/server';
import { prisma } from '@/lib/db';

export async function GET() {
  const presets = await prisma.gamePreset.findMany();
  return NextResponse.json(presets);
}
