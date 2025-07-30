import { NextRequest, NextResponse } from 'next/server';

export async function GET(req: NextRequest, { params }: { params: { userId: string }}) {
  const { userId } = params;
  return NextResponse.json({ userId, topics: {}, last7Days: {} });
}
