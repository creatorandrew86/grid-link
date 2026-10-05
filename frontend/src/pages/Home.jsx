
export function Arrow({ diagonal = false }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.3">
      <path d={diagonal ? 'M6 18 18 6M6 6h12v12' : 'M4 12h15m-6-6 6 6-6 6'} />
    </svg>
  );
}

function SolarArray() {
  return (
    <svg className="solar-array" viewBox="0 0 560 320" role="img" aria-label="Technical drawing of connected solar panels">
      <g stroke="#333" strokeWidth="1" fill="none"><path d="M0 260h560M0 290h560M60 320V0M180 320V0M300 320V0M420 320V0M540 320V0" /></g>
      <g transform="translate(78 34)">
        <path d="m0 142 62-118h344l-62 118z" fill="#111" stroke="#afafaf" />
        {Array.from({ length: 6 }, (_, x) =>
          Array.from({ length: 4 }, (_, y) => (
            <path key={`${x}-${y}`} d={`m${10 + x * 56 + y * 14} ${132 - y * 28} 11-21h46l-11 21z`} fill="#242424" stroke="#4b4b4b" strokeWidth="0.7" />
          ))
        )}
        <path d="M0 142v8h344v-8m0 8 62-118v-8M26 150v62m294-62v62M26 201h294" fill="none" stroke="#777" strokeWidth="2" />
        <path d="M170 150v78h145v26" fill="none" stroke="#afafaf" />
        <rect x="290" y="254" width="50" height="34" rx="3" fill="#111" stroke="#afafaf" />
        <path d="M301 266h28m-28 8h18" stroke="#777" />
      </g>
      <text x="400" y="304" fill="#afafaf" fontSize="10" fontFamily="monospace">PV / COMMUNITY SUPPLY</text>
    </svg>
  );
}

function GlobalStyles() {
  return (
    <style>{`
      :root {
        --yellow: #fff313;
        --white: #eeeeee;
        --carbon: #333333;
        --line: #4b4b4b;
        --muted: #afafaf;
        --gutter: clamp(24px, 4.2vw, 80px);
      }
      .dark { background: #000; color: var(--white); }
      .light { background: var(--white); color: #000; }
      .hero { padding: 32px var(--gutter) 0; }
      .rate-grid { display: grid; grid-template-columns: repeat(4, 1fr); border-top: 1px solid var(--line); padding: 28px 0 32px; }
      .rate { padding-left: 24px; border-left: 1px solid var(--line); }
      .savings-band { display: flex; align-items: center; gap: 48px; padding: 38px var(--gutter); background: var(--yellow); color: #000; }
      .community, .pricing { padding: 100px var(--gutter) 100px; }
    `}</style>
  );
}

export default function Home({ summary, refresh, busy, error, member, onNavigate }) {
  return (
    <main id="overview">
      <GlobalStyles />
      <section className="hero dark">
        <div className="hero-top">
          <p className="eyebrow">COMMUNITY ENERGY / 001</p>
          <span className="small-tag">COMMUNITY STORAGE</span>
        </div>
        <div className="hero-body">
          <div>
            <h1>Your neighbourhood.<br />Your energy.</h1>
            <p className="hero-copy">Understand your community's energy.<br />Find the right shared battery together.</p>
            <button className="text-link" onClick={() => onNavigate(member ? 'account' : 'signup')} style={{ background: 'none', border: 'none', borderBottom: '1px solid var(--line)', cursor: 'pointer', color: 'inherit', padding: '0 0 7px' }}>
              {member ? 'View community analysis' : 'Join your community'}<Arrow diagonal />
            </button>
          </div>
          <SolarArray />
        </div>
      </section>
      {error && <div className="messages"><div className="error global-error" role="alert">{error}<button className="button" onClick={refresh} disabled={busy}>Try again</button></div></div>}
      <section className="community light" id="community">
        <div className="section-heading">
          <div><p className="eyebrow">01 / YOUR COMMUNITY</p><h2>Decide together.</h2></div>
          {summary && <span className="small-tag">{summary.participant_count} MEMBERS</span>}
        </div>
        <p className="section-copy">See battery sizes and technologies compared for your current community, including ROI, payback and two ways to share the cost. If your community declines a battery, review estimates for eligible communities before choosing whether to switch.</p>
        <button className="button black" onClick={() => onNavigate(member ? 'account' : 'signup')}>{member ? 'Open my community' : 'Sign in or join'}<Arrow diagonal /></button>
      </section>
      <section className="pricing dark" id="pricing">
        <div className="section-heading">
          <div><p className="eyebrow">02 / DATA SOURCES</p><h2>Analysis from community data.</h2></div>
        </div>
        <p className="section-copy">Consumption and solar generation come from recorded community measurements. Import costs and export credits come from interval contract tariffs. Battery specifications and installed costs come from sourced equipment quotes.</p>
        <p className="muted">The analysis shows its sources and measurement coverage. Missing data is reported in your account. Forecast feeds must be connected and validated before forecast-based predictions can be shown.</p>
        <button className="button primary" onClick={() => onNavigate(member ? 'account' : 'signup')}>View community battery analysis<Arrow /></button>
      </section>
    </main>
  );
}
