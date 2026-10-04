export default function Terms({ onNavigate }) {
  return (
    <div className="terms-page dark" style={{ minHeight: 'calc(100vh - 85px)', padding: '60px var(--gutter)', background: '#000000', color: '#eeeeee' }}>
      <div style={{ maxWidth: '820px', margin: '0 auto' }}>
        <button
          className="text-button"
          onClick={() => onNavigate('home')}
          style={{ marginBottom: '24px', display: 'inline-flex', alignItems: 'center', gap: '8px' }}
        >
          ← Return to dashboard
        </button>

        <header style={{ marginBottom: '40px', borderBottom: '1px solid var(--carbon)', paddingBottom: '24px' }}>
          <p className="eyebrow" style={{ color: 'var(--yellow)', marginBottom: '8px' }}>LEGAL & COMPLIANCE</p>
          <h1 style={{ fontSize: ' clamp(36px, 4vw, 54px)', fontWeight: 300 }}>Terms and Conditions</h1>
          <p className="muted" style={{ marginTop: '12px' }}>Last updated: October 2026</p>
        </header>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '32px', lineHeight: 1.7 }}>
          <section style={{ border: '1px solid var(--line)', borderRadius: '9px', padding: '28px', background: '#0d0d0d' }}>
            <h2 style={{ fontSize: '20px', marginBottom: '12px' }}>1. Introduction & Acceptance</h2>
            <p className="muted">[Terms and conditions text will be placed here]</p>
          </section>

          <section style={{ border: '1px solid var(--line)', borderRadius: '9px', padding: '28px', background: '#0d0d0d' }}>
            <h2 style={{ fontSize: '20px', marginBottom: '12px' }}>2. Community Participation & Smart Metering</h2>
            <p className="muted">[Terms and conditions text will be placed here]</p>
          </section>

          <section style={{ border: '1px solid var(--line)', borderRadius: '9px', padding: '28px', background: '#0d0d0d' }}>
            <h2 style={{ fontSize: '20px', marginBottom: '12px' }}>3. Peer-to-Peer Energy Clearing & Tariffs</h2>
            <p className="muted">[Terms and conditions text will be placed here]</p>
          </section>

          <section style={{ border: '1px solid var(--line)', borderRadius: '9px', padding: '28px', background: '#0d0d0d' }}>
            <h2 style={{ fontSize: '20px', marginBottom: '12px' }}>4. Grid Connection & DSO Settlement</h2>
            <p className="muted">[Terms and conditions text will be placed here]</p>
          </section>

          <section style={{ border: '1px solid var(--line)', borderRadius: '9px', padding: '28px', background: '#0d0d0d' }}>
            <h2 style={{ fontSize: '20px', marginBottom: '12px' }}>5. Limitation of Liability</h2>
            <p className="muted">[Terms and conditions text will be placed here]</p>
          </section>
        </div>
      </div>
    </div>
  );
}
