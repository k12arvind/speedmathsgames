'use client';

import { useState } from 'react';

export default function Page() {
  const [username, setUsername] = useState('');
  const [message, setMessage] = useState<string>('');

  const startAsGuest = async () => {
    const res = await fetch('/api/auth/guest', { method:'POST', body: JSON.stringify({ username }) });
    if (!res.ok) return setMessage('Failed to start session');
    setMessage('Guest session created. Go to Game Setup.');
    window.location.href = '/game/setup';
  };

  return (
    <main>
      <h2>Welcome 👋</h2>
      <p>Enter a username to get started (Google login can be enabled later).</p>
      <div style={{ display:'flex', gap: 8, marginTop: 8 }}>
        <input value={username} onChange={e=>setUsername(e.target.value)} placeholder="Username" />
        <button onClick={startAsGuest}>Continue</button>
      </div>
      <p style={{ marginTop: 12 }}>{message}</p>
    </main>
  );
}
