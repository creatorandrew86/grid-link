import { useState } from 'react';
import { api, money, amount, percent } from '../api';

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

function Rate({ label, value, note }) {
  return (
    <article className="rate">
      <p className="eyebrow">{label}</p>
      <div className="rate-value">{money(value, 4)}<span>/ kWh</span></div>
      <p className="muted">{note}</p>
    </article>
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

export default function Home({ summary, refresh, busy, error, setError, notice, setNotice, memberId, setMemberId, onNavigate }) {
  const [draft, setDraft] = useState(() => summary?.settings || null);
  const [dirty, setDirty] = useState(false);
  const [preview, setPreview] = useState(false);
  const [localBusy, setLocalBusy] = useState(false);

  // Sync draft when summary changes and not dirty
  if (summary && !draft && !dirty) {
    setDraft(summary.settings);
  }

  const totals = summary?.totals;
  const selected = summary?.participants?.find((m) => m.id === memberId);
  const change = (key, val) => {
    setDraft({ ...draft, [key]: val });
    setDirty(true);
    setNotice('');
  };

  const start = summary && new Date(summary.interval_start);
  const time = (d) => d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
  const interval = start ? `${time(start)} to ${time(new Date(start.getTime() + 15 * 60000))}` : '15-minute interval';

  async function applySettings(event, save) {
    event.preventDefault();
    setLocalBusy(true);
    setError('');
    setNotice('');
    try {
      if (save) {
        await api('market-settings', 'PUT', draft);
        await refresh();
      } else {
        const result = await api('clearing-preview', 'POST', draft);
        setPreview(true);
        setDirty(true);
        setNotice('Preview updated. Save to use these settings for the community.');
      }
      if (save) {
        setPreview(false);
        setDirty(false);
        setNotice('Market settings saved.');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLocalBusy(false);
    }
  }

  return (
    <main id="overview">
      <GlobalStyles />
      <section className="hero dark">
        <div className="hero-top">
          <p className="eyebrow">COMMUNITY ENERGY / 001</p>
          <span className="status"><span className="status-dot" />Simulation</span>
        </div>
        <div className="hero-body">
          <div>
            <h1>Your neighbourhood.<br />Your energy.</h1>
            <p className="hero-copy">Buy solar from the people around you.<br />Keep more of its value in your community.</p>
            {selected ? (
              <button className="text-link" onClick={() => onNavigate('account')} style={{ background: 'none', border: 'none', borderBottom: '1px solid var(--line)', cursor: 'pointer', color: 'inherit', padding: '0 0 7px' }}>
                View account analysis<Arrow diagonal />
              </button>
            ) : (
              <a className="text-link" href="#community">See the community<Arrow diagonal /></a>
            )}
          </div>
          <SolarArray />
        </div>
        <div className="market-heading">
          <span className="eyebrow">THE CURRENT MARKET</span>
          <span className="muted">{interval} · {preview ? 'Unsaved preview' : 'Estimated 15-minute interval'}</span>
        </div>
        {summary ? (
          <div className="rate-grid">
            <Rate label="GRID IMPORT" value={summary.settings.grid_buy} note="The standard buying tariff" />
            <Rate label="GRID EXPORT" value={summary.settings.grid_sell} note="The standard selling tariff" />
            <Rate label="LOCAL BUYING" value={summary.rates.buyer_rate} note="Includes the buyer's transport share" />
            <Rate label="LOCAL SELLING" value={summary.rates.seller_rate} note="After the seller's transport share" />
          </div>
        ) : (
          <div className="loading" role="status">{error ? 'The market is unavailable.' : 'Connecting to your community…'}</div>
        )}
      </section>

      <div className="messages" aria-live="polite">
        {error && (
          <div className="error global-error" role="alert">
            {error}
            <button className="button" onClick={summary ? () => setError('') : refresh} disabled={busy || localBusy}>
              {summary ? 'Dismiss' : 'Try again'}
            </button>
          </div>
        )}
        {notice && <p className="notice">{notice}</p>}
        {preview && !notice && <p className="notice">You are viewing an unsaved pricing preview.</p>}
      </div>

      {summary && (
        <>
          <section className="savings-band" aria-label="Community savings">
            <div>
              <p className="eyebrow">VALUE KEPT IN THE COMMUNITY</p>
              <h2>{money(totals.benefit)}<span>saved this interval</span></h2>
            </div>
            <p>{amount(totals.local_traded_kwh)} kWh traded locally.<br />{summary.participants.length} members sharing the benefit.</p>
            {selected ? (
              <button
                className="circle-link"
                onClick={() => onNavigate('account')}
                aria-label="View account analysis"
                style={{ background: 'none', cursor: 'pointer' }}
              >
                <Arrow diagonal />
              </button>
            ) : (
              <a className="circle-link" href="#community" aria-label="View community energy flow"><Arrow diagonal /></a>
            )}
          </section>

          {selected ? (
            <section className="account-callout dark" style={{ padding: '60px var(--gutter)', borderTop: '1px solid var(--carbon)' }}>
              <div style={{ maxWidth: '1080px', margin: '0 auto', border: '1px solid var(--line)', borderRadius: '9px', padding: '32px', background: '#0d0d0d', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '24px', flexWrap: 'wrap' }}>
                <div>
                  <p className="eyebrow" style={{ color: 'var(--yellow)', marginBottom: '8px' }}>MEMBER ACCOUNT ACTIVE</p>
                  <h2 style={{ fontSize: '28px', marginBottom: '8px' }}>{selected.name}</h2>
                  <p className="muted">Your 15-minute interval settlement and meter analysis are in your account portal.</p>
                </div>
                <button className="button primary" onClick={() => onNavigate('account')}>
                  View account analysis
                  <Arrow diagonal />
                </button>
              </div>
            </section>
          ) : (
            <section className="community light" id="community">
              <div className="section-heading">
                <div>
                  <p className="eyebrow">01 / ENERGY FLOW</p>
                  <h2>Solar, closer to home.</h2>
                </div>
                <button className="button outline" onClick={refresh} disabled={busy || dirty || localBusy}>
                  {busy || localBusy ? 'Updating…' : 'Refresh market'}
                  <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <path d="M20 10a8 8 0 1 0-2 8M20 4v6h-6" />
                  </svg>
                </button>
              </div>
              <p className="section-copy">Solar powers each producer's own demand first. The community shares the surplus; the grid covers any gap.</p>
              {!summary.trade_enabled && <p className="trade-warning" role="status">{summary.trade_note}</p>}
              <div className="flow-grid">
                <article className="flow-main">
                  <div className="panel-top"><h3>This 15-minute interval</h3><span className="small-tag">ESTIMATED</span></div>
                  <div className="flow-diagram">
                    <div className="flow-node">
                      <span className="node-code">PV</span><p>Solar produced</p><strong>{amount(totals.generation_kwh)}<small>kWh</small></strong>
                    </div>
                    <div className="flow-connector">
                      <span>{amount(totals.self_consumed_kwh)} kWh used<br />by producers</span><Arrow />
                    </div>
                    <div className="flow-node">
                      <span className="node-code">GL</span><p>Shared locally</p><strong>{amount(totals.local_traded_kwh)}<small>kWh</small></strong>
                    </div>
                    <div className="flow-connector">
                      <span>{percent(totals.local_coverage)} of remaining<br />demand covered</span><Arrow />
                    </div>
                    <div className="flow-node">
                      <span className="node-code">kW</span><p>Community demand</p><strong>{amount(totals.load_kwh)}<small>kWh</small></strong>
                    </div>
                  </div>
                  <div className="flow-footer">
                    <span>From the grid <b>{amount(totals.grid_import_kwh)} kWh</b></span>
                    <span>Exported to the grid <b>{amount(totals.grid_export_kwh)} kWh</b></span>
                    <span>Transport collected <b>{money(totals.transport_collected, 4)}</b></span>
                  </div>
                </article>
                <article className="bill-panel">
                  <p className="eyebrow">COMMUNITY BILL</p>
                  <h3>A smaller net bill.</h3>
                  <div className="bill-line"><span>Standard grid</span><span>{money(totals.benchmark_bill)}</span></div>
                  <div className="bill-bar"><span style={{ width: '100%' }} /></div>
                  <div className="bill-line"><span>With local sharing</span><span>{money(totals.optimized_bill)}</span></div>
                  <div className="bill-bar local">
                    <span style={{ width: `${totals.benchmark_bill > 0 && totals.optimized_bill >= 0 ? Math.max(2, (totals.optimized_bill / totals.benchmark_bill) * 100) : 100}%` }} />
                  </div>
                  <p className="form-note">Net cost after export earnings. Negative bills mean earnings. Transport is included.</p>
                </article>
              </div>

              <div className="ledger-heading" id="ledger">
                <div><p className="eyebrow">02 / COMMUNITY LEDGER</p><h2>Everyone's share.</h2></div>
                <span className="muted">{summary.participants.length} members · EUR per interval</span>
              </div>
              <div className="table-scroll">
                <table>
                  <caption className="sr-only">Estimated member energy and bills for the current 15-minute interval</caption>
                  <thead>
                    <tr>
                      <th scope="col">Member</th>
                      <th scope="col">Role</th>
                      <th scope="col">Local energy</th>
                      <th scope="col">Grid bill</th>
                      <th scope="col">GridLink bill</th>
                      <th scope="col">Benefit</th>
                    </tr>
                  </thead>
                  <tbody>
                    {summary.participants.map((member) => (
                      <tr key={member.id} className={member.id === memberId ? 'selected-row' : ''}>
                        <th scope="row">
                          <button
                            className="member-button"
                            onClick={() => {
                              setMemberId(member.id);
                              try { localStorage.setItem('gridlink-member', member.id); } catch {}
                            }}
                          >
                            <span className="member-avatar">{member.name.slice(0, 2).toUpperCase()}</span>
                            {member.name}
                            {member.id === memberId && <span className="you-tag">selected</span>}
                          </button>
                        </th>
                        <td><span className="role-label">{member.type === 'prosumer' ? 'Prosumer' : 'Consumer'}</span></td>
                        <td>
                          {amount(member.local_sold_kwh || member.local_bought_kwh)} kWh{' '}
                          <span className="muted">{member.local_sold_kwh > 0 ? 'sold' : member.local_bought_kwh > 0 ? 'bought' : ''}</span>
                        </td>
                        <td>{money(member.benchmark_bill)}</td>
                        <td>{money(member.optimized_bill)}</td>
                        <td>+{money(member.benefit)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {!summary.participants.length && <p className="empty">The community is empty. Join to run the first interval.</p>}
              </div>
              <p className="ledger-note">Select a member to see their bill above. This is a shared demo; members are saved in the community database.</p>
              <div className="join-row">
                <p>Producing solar? Buying electricity?<br />There's room for both.</p>
                <button className="button black" onClick={() => onNavigate('signup')}>
                  Join community<Arrow diagonal />
                </button>
              </div>
            </section>
          )}

          {draft && (
            <section className="pricing dark" id="pricing">
              <div className="section-heading">
                <div><p className="eyebrow">{selected ? '02 / MARKET SETTINGS' : '03 / MARKET SETTINGS'}</p><h2>Set the terms.</h2></div>
                <span className="small-tag">{dirty ? 'UNSAVED CHANGES' : 'SAVED SETTINGS'}</span>
              </div>
              <div className="pricing-grid">
                <div className="pricing-explanation">
                  <h3>A price between<br />buying and selling.</h3>
                  <p>The price weight sets how much of the gap between grid tariffs goes to the seller. At 0.60, the clearing price sits 60% of the way from the export tariff to the import tariff.</p>
                  <div className="formula">
                    <span>Clearing price</span>
                    <p>Export + weight × (import − export)</p>
                    <strong>{money(summary.rates.clearing_price, 4)} <small>/ kWh</small></strong>
                  </div>
                  <p>Transport is charged once per traded kWh. The buyer pays their share on top of the clearing price. The seller's share comes out of their earnings.</p>
                  <dl className="fee-breakdown">
                    <div><dt>Buyer pays transport</dt><dd>{money(summary.rates.buyer_transport_fee, 4)} / kWh</dd></div>
                    <div><dt>Seller pays transport</dt><dd>{money(summary.rates.seller_transport_fee, 4)} / kWh</dd></div>
                  </dl>
                  <p className="form-note">These are sample tariffs for a simulation. Settings apply to the shared community. Solar output is capacity × the output factor.</p>
                </div>
                <form className="settings-form" onSubmit={(e) => applySettings(e, true)}>
                  <fieldset disabled={busy || localBusy}>
                    <div className="input-pair">
                      <label>Grid import (€ / kWh)<input type="number" min="0" max="10" step="0.001" required value={draft.grid_buy} onChange={(e) => change('grid_buy', e.target.value === '' ? '' : Number(e.target.value))} /></label>
                      <label>Grid export (€ / kWh)<input type="number" min="0" max="10" step="0.001" required value={draft.grid_sell} onChange={(e) => change('grid_sell', e.target.value === '' ? '' : Number(e.target.value))} /></label>
                    </div>
                    <label htmlFor="price-weight" className="range-label">Price weight <output>{Number(draft.price_weight).toFixed(2)}</output></label>
                    <input id="price-weight" type="range" min="0" max="1" step="0.01" value={draft.price_weight} onChange={(e) => change('price_weight', Number(e.target.value))} />
                    <div className="range-ends"><span>Closer to grid export</span><span>Closer to grid import</span></div>
                    <label htmlFor="transport">Transport fee (€ / kWh)</label>
                    <input id="transport" type="number" min="0" max="10" step="0.001" required value={draft.transport_fee} onChange={(e) => change('transport_fee', e.target.value === '' ? '' : Number(e.target.value))} />
                    <label htmlFor="transport-share" className="range-label">Buyer transport share <output>{percent(draft.buyer_transport_share)}</output></label>
                    <input id="transport-share" type="range" min="0" max="1" step="0.01" value={draft.buyer_transport_share} onChange={(e) => change('buyer_transport_share', Number(e.target.value))} />
                    <div className="range-ends"><span>Seller pays {percent(1 - draft.buyer_transport_share)}</span><span>Buyer pays {percent(draft.buyer_transport_share)}</span></div>
                    <label htmlFor="solar-factor" className="range-label">Solar output factor <output>{percent(draft.solar_yield_factor)}</output></label>
                    <input id="solar-factor" type="range" min="0" max="1" step="0.01" value={draft.solar_yield_factor} onChange={(e) => change('solar_yield_factor', Number(e.target.value))} />
                    <div className="range-ends"><span>No solar</span><span>Full rated output</span></div>
                    <div className="settings-actions">
                      <button className="button primary" type="submit" disabled={!dirty || localBusy}>{localBusy ? 'Updating…' : 'Save settings'}<Arrow /></button>
                      <button className="button" type="button" disabled={!dirty || localBusy} onClick={(e) => { if (e.currentTarget.form.reportValidity()) applySettings(e, false); }}>Preview</button>
                      <button className="text-button" type="button" disabled={!dirty || localBusy} onClick={refresh}>Discard</button>
                    </div>
                    <p className="form-note">Preview recalculates the dashboard. Save keeps the settings after a restart.</p>
                  </fieldset>
                </form>
              </div>
            </section>
          )}
        </>
      )}
    </main>
  );
}

