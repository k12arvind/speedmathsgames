import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/db';
import { StartGameSchema } from '@/lib/validators';

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const parsed = StartGameSchema.safeParse(body);
    if (!parsed.success) {
      return NextResponse.json({ error: 'Invalid request data', details: parsed.error.format() }, { status: 400 });
    }

    const { presetId, timeLimitSec, selectedTopics, difficulty } = parsed.data;
    let resolvedConfig: any = { topics: selectedTopics || ['addition','multiplication'], difficulty: difficulty || 'medium' };
    
    if (presetId) {
      const preset = await prisma.gamePreset.findUnique({ where: { id: presetId } });
      if (preset) resolvedConfig = preset.config;
    }
    
    const seed = Math.floor(Math.random()*1e9).toString();
    const cookie = req.cookies.get('smg_user');
    const user = cookie ? JSON.parse(cookie.value) : null;
    
    if (!user) {
      return NextResponse.json({ 
        error: 'not authenticated', 
        details: 'No user session found. Please go back to home page and enter username.' 
      }, { status: 401 });
    }

    const session = await prisma.gameSession.create({
      data: {
        userId: user.id,
        timeLimitSec: timeLimitSec ?? (resolvedConfig.timeLimitSec || 300),
        config: { ...resolvedConfig, seed },
        status: 'active'
      }
    });

    return NextResponse.json({ sessionId: session.id, seed, timeLimitSec: session.timeLimitSec, resolvedConfig });
  } catch (error: any) {
    console.error('Game start error:', error);
    return NextResponse.json({ 
      error: 'Failed to start game', 
      details: error.message 
    }, { status: 500 });
  }
}
