'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

export default function SetupPage() {
  const router = useRouter();
  const [topics, setTopics] = useState<string[]>(['addition','decimals']);
  const [timeLimitSec, setTimeLimitSec] = useState(120);
  const [difficulty, setDifficulty] = useState<'easy'|'medium'|'hard'>('medium');
  const [error, setError] = useState<string>('');

  const toggleTopic = (t: string) => {
    setTopics(prev => prev.includes(t) ? prev.filter(x=>x!==t) : [...prev, t]);
  };

  const start = async () => {
    setError('');
    const res = await fetch('/api/game/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        selectedTopics: topics.map(t => ({ name: t, weight: 1 })),
        timeLimitSec,
        difficulty
      })
    });
    if (!res.ok) { setError('Failed to start game.'); return; }
    const data = await res.json();
    router.push(`/game/play/${data.sessionId}?t=${Date.now()}`);
  };

  return (
    <main>
      <h2>Game Setup</h2>
      <section style={{ marginTop: 8 }}>
        <strong>Topics</strong>
        <div style={{ display:'flex', gap:8, flexWrap:'wrap', marginTop: 6 }}>
          {['addition','subtraction','multiplication','division','fractions','decimals','percentages','bodmas'].map(t => (
            <label key={t} style={{ display:'inline-flex', gap:4 }}>
              <input type="checkbox" checked={topics.includes(t)} onChange={()=>toggleTopic(t)} />
              {t}
            </label>
          ))}
        </div>
      </section>
      <section style={{ marginTop: 8 }}>
        <label>Time (seconds): <input type="number" value={timeLimitSec} min={30} max={3600} onChange={e=>setTimeLimitSec(parseInt(e.target.value||'120',10))} /></label>
      </section>
      <section style={{ marginTop: 8 }}>
        <label>Difficulty: </label>
        <select value={difficulty} onChange={e=>setDifficulty(e.target.value as any)}>
          <option value="easy">easy</option>
          <option value="medium">medium</option>
          <option value="hard">hard</option>
        </select>
      </section>
      <div style={{ marginTop: 12 }}>
        <button onClick={start}>Start</button>
        <span style={{ color:'crimson', marginLeft: 12 }}>{error}</span>
      </div>
    </main>
  );
}
