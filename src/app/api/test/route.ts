import { NextResponse } from 'next/server';

export async function GET() {
  try {
    return NextResponse.json({ 
      status: 'success',
      message: 'API is working',
      timestamp: new Date().toISOString(),
      environment: {
        hasDbUrl: !!process.env.DATABASE_URL,
        hasNextAuthUrl: !!process.env.NEXTAUTH_URL,
        hasNextAuthSecret: !!process.env.NEXTAUTH_SECRET,
        nextAuthUrl: process.env.NEXTAUTH_URL || 'not set'
      }
    });
  } catch (error: any) {
    return NextResponse.json({ 
      status: 'error',
      message: error.message
    }, { status: 500 });
  }
}