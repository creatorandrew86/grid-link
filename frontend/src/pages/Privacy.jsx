export default function Privacy({ onNavigate }) {
  return (
    <div className="privacy-page dark" style={{ minHeight: 'calc(100vh - 85px)', padding: '60px var(--gutter)', background: '#000000', color: '#eeeeee' }}>
      <div style={{ maxWidth: '820px', margin: '0 auto' }}>
        <button
          className="text-button"
          onClick={() => onNavigate('home')}
          style={{ marginBottom: '24px', display: 'inline-flex', alignItems: 'center', gap: '8px' }}
        >
          ← Return to dashboard
        </button>

        <header style={{ marginBottom: '40px', borderBottom: '1px solid var(--carbon)', paddingBottom: '24px' }}>
          <p className="eyebrow" style={{ color: 'var(--yellow)', marginBottom: '8px' }}>DATA PROTECTION & PRIVACY</p>
          <h1 style={{ fontSize: 'clamp(36px, 4vw, 54px)', fontWeight: 300 }}>Privacy Policy</h1>
          <p className="muted" style={{ marginTop: '12px' }}>Last updated: October 2026</p>
        </header>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '32px', lineHeight: 1.7 }}>
          <section style={{ border: '1px solid var(--line)', borderRadius: '9px', padding: '28px', background: '#0d0d0d' }}>
            <h2 style={{ fontSize: '20px', marginBottom: '12px' }}>1. Information We Collect</h2>
            <p className="muted">[Privacy policy text will be placed here]</p>
          </section>

          <section style={{ border: '1px solid var(--line)', borderRadius: '9px', padding: '28px', background: '#0d0d0d' }}>
            <h2 style={{ fontSize: '20px', marginBottom: '12px' }}>2. Smart Meter Telemetry & 15-Minute Data</h2>
            <p className="muted">[Privacy policy text will be placed here]</p>
          </section>

          <section style={{ border: '1px solid var(--line)', borderRadius: '9px', padding: '28px', background: '#0d0d0d' }}>
            <h2 style={{ fontSize: '20px', marginBottom: '12px' }}>3. How We Use and Share Information</h2>
            <p className="muted">[Privacy policy text will be placed here]</p>
          </section>

          <section style={{ border: '1px solid var(--line)', borderRadius: '9px', padding: '28px', background: '#0d0d0d' }}>
            <h2 style={{ fontSize: '20px', marginBottom: '12px' }}>4. Community Totals & Private Member Records</h2>
            <p className="muted">[Privacy policy text will be placed here]</p>
          </section>

          <section style={{ border: '1px solid var(--line)', borderRadius: '9px', padding: '28px', background: '#0d0d0d' }}>
            <h2 style={{ fontSize: '20px', marginBottom: '12px' }}>5. Data Security & Your Rights (GDPR)</h2>
            <p className="muted">[Privacy policy text will be placed here]</p>
          </section>
        </div>
      </div>
    </div>
  );
}
