export default function AdminHome() {
  return (
    <main>
      <h2>Admin</h2>
      <ul>
        <li><a href="/admin/topic-configs">Topic Configs</a></li>
        <li><a href="/admin/presets">Presets</a></li>
      </ul>
      <p style={{ marginTop: 12 }}>This is a starter admin area. Add auth checks and design polish.</p>
    </main>
  );
}
