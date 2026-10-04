export default function Footer({ onNavigate, storage }) {
  return (
    <footer>
      <div style={{ display: 'flex', alignItems: 'center', gap: '24px', flexWrap: 'wrap' }}>
        <a className="brand" href="#home" onClick={(e) => { e.preventDefault(); onNavigate('home'); }}>gridlink.</a>
        <p>Community energy, one interval at a time.</p>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '20px', flexWrap: 'wrap', fontSize: '12px' }}>
        <a
          href="#terms"
          onClick={(e) => { e.preventDefault(); onNavigate('terms'); }}
          style={{ color: 'var(--muted)', textDecoration: 'underline', textUnderlineOffset: '4px' }}
        >
          Terms and Conditions
        </a>
        <a
          href="#privacy"
          onClick={(e) => { e.preventDefault(); onNavigate('privacy'); }}
          style={{ color: 'var(--muted)', textDecoration: 'underline', textUnderlineOffset: '4px' }}
        >
          Privacy Policy
        </a>
        <span style={{ color: 'var(--muted)' }}>Prototype 0.1 · {storage === 'supabase' ? 'Supabase storage' : 'Local storage'}</span>
      </div>
    </footer>
  );
}
