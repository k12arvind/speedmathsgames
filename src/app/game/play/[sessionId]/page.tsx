'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

type Question = {
  id: string;
  indexInSession: number;
  topic: string;
  difficulty: string;
  prompt: string;
  inputType: string;
};

export default function PlayPage({ params }: { params: { sessionId: string } }) {
  const { sessionId } = params;
  const router = useRouter();
  const sp = useSearchParams();
  const [index, setIndex] = useState(0);
  const [question, setQuestion] = useState<Question | null>(null);
  const [answer, setAnswer] = useState('');
  const [timeLeft, setTimeLeft] = useState<number>(120);
  const [startedAt, setStartedAt] = useState<number>(Date.now());
  const [qStart, setQStart] = useState<number>(Date.now());
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    // Optional: accept time from session if passed via query or fetch session details
    setTimeLeft( Number(sp.get('time') || 120) );
    setStartedAt(Date.now());
    setQStart(Date.now());
  }, []);

  const tick = () => setTimeLeft(t => t-1);
  useEffect(() => {
    timerRef.current = setInterval(tick, 1000);
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, []);

  useEffect(() => {
    if (timeLeft <= 0) finish();
  }, [timeLeft]);

  const fetchQuestion = async (i: number) => {
    const res = await fetch(`/api/game/next?sessionId=${sessionId}&index=${i}`);
    if (!res.ok) return;
    const data = await res.json();
    setQuestion(data.question);
    setQStart(Date.now());
    setAnswer('');
  };

  useEffect(() => { fetchQuestion(index); }, [index]);

  const submit = async () => {
    if (!question) return;
    const timeTakenMs = Date.now() - qStart;
    await fetch('/api/game/answer', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sessionId, questionId: question.id, userAnswer: answer, timeTakenMs })
    });
    setIndex(index + 1);
  };

  const skip = async () => {
    if (!question) return;
    const timeTakenMs = Date.now() - qStart;
    await fetch('/api/game/skip', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sessionId, questionId: question.id, timeTakenMs })
    });
    setIndex(index + 1);
  };

  const finish = async () => {
    if (timerRef.current) clearInterval(timerRef.current);
    const res = await fetch('/api/game/finish', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sessionId })
    });
    const data = await res.json();
    router.push(`/game/review/${sessionId}`);
  };

  return (
    <main>
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center' }}>
        <h2>Play</h2>
        <div><strong>Time left:</strong> {timeLeft}s</div>
      </div>
      {question ? (
        <div style={{ marginTop: 12 }}>
          <div style={{ fontSize: 22, marginBottom: 8 }}>{question.prompt}</div>
          <input value={answer} onChange={e=>setAnswer(e.target.value)} placeholder="Type your answer" autoFocus />
          <div style={{ marginTop: 8, display:'flex', gap:8 }}>
            <button onClick={submit}>Submit</button>
            <button onClick={skip}>Skip</button>
            <button onClick={finish}>Finish</button>
          </div>
        </div>
      ) : (
        <p>Loading question...</p>
      )}
    </main>
  );
}
