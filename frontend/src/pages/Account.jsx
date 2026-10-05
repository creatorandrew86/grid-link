import { money, amount } from '../apiClient';
import { Arrow } from './Home';
import CommunityBatteryPlan from '../CommunityBatteryPlan';

export default function Account({ member, summary, loading, refresh, busy, onNavigate, onLogout, onCommunitySwitched }) {
  if (loading && !member) {
    return (
      <div className="account-page dark" style={{ minHeight: 'calc(100vh - 85px)', padding: '60px var(--gutter)' }}>
        <div style={{ maxWidth: '720px', margin: '0 auto', textAlign: 'center', padding: '60px 0' }}>
          <p className="muted">Connecting to your account and live telemetry…</p>
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

  const start = summary && new Date(summary.interval_start);
  const time = (d) => d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
  const interval = start ? `${time(start)} to ${time(new Date(start.getTime() + 15 * 60000))}` : '15-minute interval';

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

          {/* Smart Meter & Clearing Summary */}
          <article style={{ border: '1px solid var(--line)', borderRadius: '9px', padding: '28px', background: '#0d0d0d' }}>
            <p className="eyebrow" style={{ color: 'var(--muted)', marginBottom: '12px' }}>01 / COMMUNITY INTERVAL ESTIMATE</p>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px', flexWrap: 'wrap', gap: '16px' }}>
              <div>
                <h3 style={{ fontSize: '18px' }}>Community energy summary</h3>
                <p className="muted" style={{ marginTop: '4px' }}>Estimated from stored community profiles and tariffs; not live meter readings.</p>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                <span className="status"><span className="status-dot" style={{ background: '#51cf66' }} />Simulation</span>
                {refresh && (
                  <button className="button outline" onClick={refresh} disabled={busy} style={{ color: 'var(--white)', minHeight: '34px', padding: '6px 12px' }}>
                    {busy ? 'Updating…' : 'Refresh data'}
                  </button>
                )}
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '20px', borderTop: '1px solid var(--carbon)', paddingTop: '20px' }}>
              <div>
                <span className="eyebrow" style={{ color: 'var(--muted)' }}>CURRENT INTERVAL BENCHMARK</span>
                <p style={{ fontSize: '22px', marginTop: '6px' }}>{money(member.benchmark_bill || 0)}</p>
              </div>
              <div>
                <span className="eyebrow" style={{ color: 'var(--muted)' }}>OPTIMIZED GRIDLINK BILL</span>
                <p style={{ fontSize: '22px', marginTop: '6px', color: 'var(--yellow)' }}>{money(member.optimized_bill || 0)}</p>
              </div>
              <div>
                <span className="eyebrow" style={{ color: 'var(--muted)' }}>INTERVAL BENEFIT</span>
                <p style={{ fontSize: '22px', marginTop: '6px', color: '#51cf66' }}>+{money(member.benefit || 0)}</p>
              </div>
              <div>
                <span className="eyebrow" style={{ color: 'var(--muted)' }}>LOCAL ENERGY TRADED</span>
                <p style={{ fontSize: '22px', marginTop: '6px' }}>
                  {amount(member.local_sold_kwh || member.local_bought_kwh)} <span style={{ fontSize: '13px', color: 'var(--muted)' }}>kWh</span>
                </p>
              </div>
            </div>
          </article>

          {/* 15-Minute Interval Account Energy Flow */}
          <article style={{ border: '1px solid var(--line)', borderRadius: '9px', padding: '28px', background: '#0d0d0d' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px', flexWrap: 'wrap', gap: '12px' }}>
              <div>
                <p className="eyebrow" style={{ color: 'var(--muted)', marginBottom: '8px' }}>02 / 15-MINUTE INTERVAL ACTIVITY</p>
                <h3 style={{ fontSize: '20px' }}>Account energy flow</h3>
              </div>
              <span className="muted" style={{ fontFamily: 'monospace' }}>{interval}</span>
            </div>

            <div className="flow-grid" style={{ marginTop: '20px' }}>
              <div className="flow-main" style={{ border: '1px solid var(--carbon)', background: '#111' }}>
                <div className="panel-top">
                  <h3>Your energy balance</h3>
                  <span className="small-tag" style={{ color: 'var(--yellow)', borderColor: 'var(--yellow)' }}>15 MIN</span>
                </div>
                <div className="flow-diagram">
                  <div className="flow-node">
                    <span className="node-code">PV</span>
                    <p>Your generation</p>
                    <strong>{amount(member.generation_kwh)}<small>kWh</small></strong>
                  </div>
                  <div className="flow-connector">
                    <span>{amount(member.self_consumed_kwh)} kWh self-used</span>
                    <Arrow />
                  </div>
                  <div className="flow-node">
                    <span className="node-code">GL</span>
                    <p>{member.local_sold_kwh > 0 ? 'Sold to neighbours' : 'Bought from neighbours'}</p>
                    <strong>{amount(member.local_sold_kwh || member.local_bought_kwh)}<small>kWh</small></strong>
                  </div>
                  <div className="flow-connector">
                    <span>Net grid balance</span>
                    <Arrow />
                  </div>
                  <div className="flow-node">
                    <span className="node-code">kW</span>
                    <p>Your load</p>
                    <strong>{amount(member.load_kwh)}<small>kWh</small></strong>
                  </div>
                </div>
                <div className="flow-footer" style={{ borderTop: '1px solid var(--carbon)' }}>
                  <span>Imported from grid <b>{amount(member.grid_import_kwh)} kWh</b></span>
                  <span>Exported to grid <b>{amount(member.grid_export_kwh)} kWh</b></span>
                  <span>Transport fee paid <b>{money(member.transport_paid, 4)}</b></span>
                </div>
              </div>

              <div className="bill-panel" style={{ border: '1px solid var(--carbon)', background: '#111' }}>
                <p className="eyebrow" style={{ color: 'var(--muted)' }}>INTERVAL SETTLEMENT</p>
                <h3>Your interval bill</h3>
                <div className="bill-line"><span>Standard grid tariff</span><span>{money(member.benchmark_bill)}</span></div>
                <div className="bill-bar" style={{ background: 'var(--carbon)' }}><span style={{ width: '100%', background: '#666' }} /></div>
                <div className="bill-line"><span>With GridLink local clearing</span><span style={{ color: 'var(--yellow)' }}>{money(member.optimized_bill)}</span></div>
                <div className="bill-bar local" style={{ background: 'var(--carbon)' }}>
                  <span style={{ background: 'var(--yellow)', width: `${member.benchmark_bill !== 0 ? Math.min(100, Math.max(2, Math.abs(member.optimized_bill / member.benchmark_bill) * 100)) : 100}%` }} />
                </div>
                <p className="form-note" style={{ color: 'var(--muted)' }}>
                  Net cost after local trades and grid adjustments. Negative bill indicates net earnings.
                </p>
              </div>
            </div>
          </article>
        </div>
      </div>
    </div>
  );
}
