'use client';

import { useEffect, useState } from 'react';

type ReviewItem = {
  index: number;
  topic: string;
  prompt: string;
  userAnswer: string;
  correctAnswer: string | null;
  timeTakenMs: number | null;
  wasSkipped: boolean;
  isCorrect: boolean;
};

export default function ReviewPage({ params }: { params: { sessionId: string } }) {
  const { sessionId } = params;
  const [summary, setSummary] = useState<any>(null);

  useEffect(() => {
    (async () => {
      const res = await fetch('/api/game/finish', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ sessionId }) });
      const data = await res.json();
      setSummary(data);
    })();
  }, [sessionId]);

  if (!summary) return <main><p>Loading summary...</p></main>;

  return (
    <main>
      <h2>Review</h2>
      <p>Score: {summary.score} | Accuracy: {(summary.accuracy*100).toFixed(0)}% | Avg time: {summary.avgTimeMs} ms</p>
      <table style={{ width:'100%', borderCollapse:'collapse', marginTop: 8 }}>
        <thead>
          <tr>
            <th style={{ textAlign:'left' }}>#</th>
            <th style={{ textAlign:'left' }}>Topic</th>
            <th style={{ textAlign:'left' }}>Prompt</th>
            <th style={{ textAlign:'left' }}>Your Answer</th>
            <th style={{ textAlign:'left' }}>Correct</th>
            <th style={{ textAlign:'left' }}>Time (ms)</th>
            <th style={{ textAlign:'left' }}>Result</th>
          </tr>
        </thead>
        <tbody>
          {summary.review?.map((r: ReviewItem) => (
            <tr key={r.index}>
              <td>{r.index+1}</td>
              <td>{r.topic}</td>
              <td>{r.prompt}</td>
              <td>{r.userAnswer}</td>
              <td>{r.correctAnswer}</td>
              <td>{r.timeTakenMs ?? ''}</td>
              <td>{r.wasSkipped ? 'Skipped' : (r.isCorrect ? 'Correct' : 'Incorrect')}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div style={{ marginTop: 12 }}>
        <a href="/game/setup">Play again</a>
      </div>
    </main>
  );
}
