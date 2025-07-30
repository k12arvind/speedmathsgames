import './globals.css';

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header>
          <div style={{ maxWidth: '1200px', margin: '0 auto', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h1>🧮 SpeedMathsGames.com</h1>
            <nav>
              <a href="/">Home</a>
              <a href="/game/setup">Play</a>
              <a href="/admin">Admin</a>
            </nav>
          </div>
        </header>
        {children}
      </body>
    </html>
  );
}
