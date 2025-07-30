import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/db';

export async function POST(req: NextRequest) {
  const body = await req.text();
  let username = '';
  try {
    const parsed = JSON.parse(body || '{}');
    username = (parsed.username || '').toString().trim();
  } catch {}
  if (!username) return NextResponse.json({ error: 'username required' }, { status: 400 });

  // ensure uniqueness by suffixing if needed
  let finalUsername = username;
  for (let i=0; i<5; i++) {
    const exists = await prisma.user.findUnique({ where: { username: finalUsername } });
    if (!exists) break;
    finalUsername = `${username}${Math.floor(100 + Math.random()*900)}`;
  }
  const user = await prisma.user.create({ data: { username: finalUsername } });
  // Minimal session via cookie (for demo; replace with proper auth in prod)
  const res = NextResponse.json({ user: { id: user.id, username: user.username } });
  res.cookies.set('smg_user', JSON.stringify({ id: user.id, username: user.username }), { httpOnly: true, path: '/' });
  return res;
}
