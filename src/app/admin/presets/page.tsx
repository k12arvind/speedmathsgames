'use client';
import { useEffect, useState } from 'react';

export default function PresetsPage() {
  const [jsonText, setJsonText] = useState('[]');
  const [message, setMessage] = useState('');

  useEffect(() => {
    fetch('/api/presets').then(r=>r.json()).then(d=>setJsonText(JSON.stringify(d, null, 2)));
  }, []);

  const save = async () => {
    try {
      const payload = JSON.parse(jsonText);
      const res = await fetch('/api/admin/presets', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) });
      setMessage(res.ok ? 'Saved' : 'Save failed');
    } catch (e:any) {
      setMessage('Invalid JSON: ' + e.message);
    }
  };

  return (
    <main>
      <h2>Game Presets (JSON)</h2>
      <textarea value={jsonText} onChange={e=>setJsonText(e.target.value)} style={{ width:'100%', height: 360, fontFamily:'monospace' }} />
      <div style={{ marginTop: 8 }}>
        <button onClick={save}>Save</button> <span>{message}</span>
      </div>
    </main>
  );
}
