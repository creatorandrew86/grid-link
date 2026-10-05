import CommunityBatteryPlan from '../CommunityBatteryPlan';

export default function Account({ member, loading, onNavigate, onLogout, onCommunitySwitched }) {
  if (loading && !member) {
    return (
      <div className="account-page dark" style={{ minHeight: 'calc(100vh - 85px)', padding: '60px var(--gutter)' }}>
        <div style={{ maxWidth: '720px', margin: '0 auto', textAlign: 'center', padding: '60px 0' }}>
          <p className="muted">Connecting to your account and community data…</p>
        </div>
      </div>
    );
  }

  if (!member) {
    return (
      <div className="account-page dark" style={{ minHeight: 'calc(100vh - 85px)', padding: '60px var(--gutter)' }}>
        <div style={{ maxWidth: '720px', margin: '0 auto' }}>
          <button
            className="text-button"
            onClick={() => onNavigate('home')}
            style={{ marginBottom: '24px', display: 'inline-flex', alignItems: 'center', gap: '8px' }}
          >
            ← Return to dashboard
          </button>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '32px' }}>
            <div>
              <p className="eyebrow" style={{ color: 'var(--yellow)', marginBottom: '8px' }}>MEMBER PORTAL</p>
              <h1>Account and meter</h1>
            </div>
          </div>

          <div style={{ border: '1px solid var(--line)', borderRadius: '9px', padding: '48px', textAlign: 'center', background: '#0a0a0a' }}>
            <p className="muted" style={{ marginBottom: '20px' }}>No community member is currently signed in.</p>
            <button className="button primary" onClick={() => onNavigate('signup')}>
              Sign in or join community
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="account-page dark" style={{ minHeight: 'calc(100vh - 85px)', padding: '60px var(--gutter)' }}>
      <div style={{ maxWidth: '1080px', margin: '0 auto' }}>
        <button
          className="text-button"
          onClick={() => onNavigate('home')}
          style={{ marginBottom: '24px', display: 'inline-flex', alignItems: 'center', gap: '8px' }}
        >
          ← Return to dashboard
        </button>

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '32px', flexWrap: 'wrap', gap: '16px' }}>
          <div>
            <p className="eyebrow" style={{ color: 'var(--yellow)', marginBottom: '8px' }}>MEMBER PORTAL</p>
            <h1>Account and meter</h1>
          </div>
          <button className="button outline" onClick={onLogout} style={{ color: 'var(--white)' }}>
            Sign out
          </button>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '28px' }}>
          <CommunityBatteryPlan key={`${member.id}-${member.community_id}`} memberId={member.id} onSwitched={onCommunitySwitched} />
          {/* Identity Card */}
          <article style={{ border: '1px solid var(--line)', borderRadius: '9px', padding: '28px', background: '#0d0d0d' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '18px', marginBottom: '24px', flexWrap: 'wrap' }}>
              <div
                style={{
                  width: '56px',
                  height: '56px',
                  borderRadius: '50%',
                  background: 'var(--yellow)',
                  color: '#000',
                  display: 'grid',
                  placeItems: 'center',
                  fontSize: '20px',
                  fontWeight: '300',
                }}
              >
                {member.name.slice(0, 2).toUpperCase()}
              </div>
              <div>
                <h2 style={{ fontSize: '24px' }}>{member.name}</h2>
                <p className="muted">{member.email || 'account@gridlink.energy'}</p>
              </div>
              <span className="small-tag" style={{ marginLeft: 'auto', color: 'var(--yellow)' }}>
                {member.type === 'prosumer' ? 'PROSUMER (SOLAR)' : 'CONSUMER'}
              </span>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '16px', borderTop: '1px solid var(--carbon)', paddingTop: '20px' }}>
              <div>
                <span className="eyebrow" style={{ color: 'var(--muted)' }}>GRID POD (POINT OF DELIVERY)</span>
                <p style={{ fontFamily: 'monospace', fontSize: '15px', marginTop: '6px' }}>{member.pod || 'Not registered'}</p>
              </div>
              <div>
                <span className="eyebrow" style={{ color: 'var(--muted)' }}>REGISTERED LOAD PROFILE</span>
                <p style={{ fontSize: '16px', marginTop: '6px' }}>{member.load_kw} kW</p>
              </div>
              <div>
                <span className="eyebrow" style={{ color: 'var(--muted)' }}>SOLAR PV CAPACITY</span>
                <p style={{ fontSize: '16px', marginTop: '6px' }}>{member.solar_kwp ? `${member.solar_kwp} kWp` : 'None (Consumer)'}</p>
              </div>
            </div>
          </article>

        </div>
      </div>
    </div>
  );
}
