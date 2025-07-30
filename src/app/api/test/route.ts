import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/db';

export async function GET(req: NextRequest) {
  try {
    // Test database connection
    const userCount = await prisma.user.count();
    
    return NextResponse.json({ 
      status: 'success',
      database: 'connected',
      userCount,
      environment: {
        hasDbUrl: !!process.env.DATABASE_URL,
        hasNextAuthUrl: !!process.env.NEXTAUTH_URL,
        hasNextAuthSecret: !!process.env.NEXTAUTH_SECRET,
      }
    });
  } catch (error: any) {
    return NextResponse.json({ 
      status: 'error',
      message: error.message,
      environment: {
        hasDbUrl: !!process.env.DATABASE_URL,
        hasNextAuthUrl: !!process.env.NEXTAUTH_URL,
        hasNextAuthSecret: !!process.env.NEXTAUTH_SECRET,
      }
    }, { status: 500 });
  }
}