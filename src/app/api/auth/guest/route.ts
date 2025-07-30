import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/db';

export async function POST(req: NextRequest) {
  try {
    const body = await req.text();
    let username = '';
    
    try {
      const parsed = JSON.parse(body || '{}');
      username = (parsed.username || '').toString().trim();
    } catch (e) {
      return NextResponse.json({ error: 'Invalid JSON in request' }, { status: 400 });
    }
    
    if (!username) {
      return NextResponse.json({ error: 'username required' }, { status: 400 });
    }

    // ensure uniqueness by suffixing if needed
    let finalUsername = username;
    for (let i=0; i<5; i++) {
      const exists = await prisma.user.findUnique({ where: { username: finalUsername } });
      if (!exists) break;
      finalUsername = `${username}${Math.floor(100 + Math.random()*900)}`;
    }
    
    const user = await prisma.user.create({ data: { username: finalUsername } });
    
    // Create response with user data
    const userData = { id: user.id, username: user.username };
    const res = NextResponse.json({ user: userData, success: true });
    
    // Set cookie with better settings for Vercel
    res.cookies.set('smg_user', JSON.stringify(userData), { 
      httpOnly: true, 
      path: '/',
      secure: true,
      sameSite: 'lax',
      maxAge: 60 * 60 * 24 * 7 // 7 days
    });
    
    return res;
  } catch (error: any) {
    console.error('Guest auth error:', error);
    return NextResponse.json({ 
      error: 'Failed to create user', 
      details: error.message 
    }, { status: 500 });
  }
}
