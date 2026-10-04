import { useEffect, useRef, useState } from 'react';
import BatteryPlanner from './BatteryPlanner.jsx';

const money = (value, digits = 3) => new Intl.NumberFormat('en-IE', { style: 'currency', currency: 'EUR', minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value);
const amount = (value) => Number(value).toLocaleString('en-IE', { maximumFractionDigits: 3 });
const percent = (value) => `${Math.round(value * 100)}%`;

async function api(path, method = 'GET', body) {
  const response = await fetch(`/api/${path}`, { method, headers: body ? { 'Content-Type': 'application/json' } : {}, body: body ? JSON.stringify(body) : undefined });
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = data?.detail;
    throw new Error(typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map((item) => item.msg).join(' ') : 'Could not reach GridLink. Check that the backend is running.');
  }
  return data;
}

function Arrow({ diagonal = false }) {
  return <svg aria-hidden="true" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.3"><path d={diagonal ? 'M6 18 18 6M6 6h12v12' : 'M4 12h15m-6-6 6 6-6 6'} /></svg>;
}

function SolarArray() {
  return <svg className="solar-array" viewBox="0 0 560 320" role="img" aria-label="Technical drawing of connected solar panels">
    <g stroke="#333" strokeWidth="1" fill="none"><path d="M0 260h560M0 290h560M60 320V0M180 320V0M300 320V0M420 320V0M540 320V0" /></g>
    <g transform="translate(78 34)">
      <path d="m0 142 62-118h344l-62 118z" fill="#111" stroke="#afafaf" />
      {Array.from({ length: 6 }, (_, x) => Array.from({ length: 4 }, (_, y) => <path key={`${x}-${y}`} d={`m${10 + x * 56 + y * 14} ${132 - y * 28} 11-21h46l-11 21z`} fill="#242424" stroke="#4b4b4b" strokeWidth="0.7" />))}
      <path d="M0 142v8h344v-8m0 8 62-118v-8M26 150v62m294-62v62M26 201h294" fill="none" stroke="#777" strokeWidth="2" />
      <path d="M170 150v78h145v26" fill="none" stroke="#afafaf" />
      <rect x="290" y="254" width="50" height="34" rx="3" fill="#111" stroke="#afafaf" />
      <path d="M301 266h28m-28 8h18" stroke="#777" />
    </g>
    <text x="400" y="304" fill="#afafaf" fontSize="10" fontFamily="monospace">PV / COMMUNITY SUPPLY</text>
  </svg>;
}

function Rate({ label, value, note }) {
  return <article className="rate"><p className="eyebrow">{label}</p><div className="rate-value">{money(value, 4)}<span>/ kWh</span></div><p className="muted">{note}</p></article>;
}

function Signup({ onClose, onJoined }) {
  const dialog = useRef(null);
  const [type, setType] = useState('consumer');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => { dialog.current.showModal(); }, []);
  async function submit(event) {
    event.preventDefault();
    setBusy(true); setError('');
    const fields = new FormData(event.currentTarget);
    try {
      const member = await api('signup', 'POST', { name: fields.get('name'), type, load_kw: Number(fields.get('load_kw')), solar_kwp: type === 'prosumer' ? Number(fields.get('solar_kwp')) : 0 });
      onJoined(member);
    } catch (error) { setError(error.message); setBusy(false); }
  }
  return <dialog ref={dialog} onCancel={(event) => { if (busy) event.preventDefault(); else onClose(); }} aria-labelledby="signup-title">
    <div className="dialog-top"><span className="eyebrow">JOIN GRIDLINK</span><button className="icon-button" aria-label="Close signup" onClick={onClose} disabled={busy}>×</button></div>
    <h2 id="signup-title">A place in the community.</h2><p className="muted">Add your home or business to see how local solar changes your bill.</p>
    <form onSubmit={submit}>
      <fieldset disabled={busy}>
        <label htmlFor="member-name">Home or business name</label><input id="member-name" name="name" placeholder="e.g. Alex's home" minLength="2" maxLength="80" required autoFocus />
        <span className="field-label" id="member-type-label">How will you participate?</span>
        <div className="role-picker" role="group" aria-labelledby="member-type-label">
          <button type="button" className={type === 'consumer' ? 'chosen' : ''} aria-pressed={type === 'consumer'} onClick={() => setType('consumer')}>Consumer<span>I buy electricity</span></button>
          <button type="button" className={type === 'prosumer' ? 'chosen' : ''} aria-pressed={type === 'prosumer'} onClick={() => setType('prosumer')}>Prosumer<span>I also produce solar</span></button>
        </div>
        <label htmlFor="member-load">Average demand <span>(kW)</span></label><input id="member-load" name="load_kw" type="number" min="0" max="1000" step="0.01" defaultValue="2" required />
        {type === 'prosumer' && <><label htmlFor="member-solar">Installed solar capacity <span>(kWp)</span></label><input id="member-solar" name="solar_kwp" type="number" min="0.01" max="1000" step="0.01" defaultValue="5" required /></>}
        <p className="form-note">This prototype uses estimated demand and solar output. No meter or payment account is connected.</p>
        {error && <p className="error" role="alert">{error}</p>}
        <button className="button primary w-full" type="submit">{busy ? 'Joining…' : 'Join the community'}<Arrow /></button>
      </fieldset>
    </form>
  </dialog>;
}

export default function App() {
  const [summary, setSummary] = useState(null);
  const [draft, setDraft] = useState(null);
  const [dirty, setDirty] = useState(false);
  const [preview, setPreview] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [showSignup, setShowSignup] = useState(false);
  const [memberId, setMemberId] = useState(() => { try { return localStorage.getItem('gridlink-member') || ''; } catch { return ''; } });

  async function refresh() {
    setBusy(true); setError('');
    try { const result = await api('clearing-summary'); setSummary(result); setDraft(result.settings); setDirty(false); setPreview(false); }
    catch (error) { setError(error.message); }
    finally { setBusy(false); }
  }
  useEffect(() => { refresh(); }, []);
  useEffect(() => {
    if (dirty || busy || showSignup) return;
    const timer = setInterval(refresh, 30000);
    return () => clearInterval(timer);
  }, [dirty, busy, showSignup]);

  async function applySettings(event, save) {
    event.preventDefault(); setBusy(true); setError(''); setNotice('');
    try {
      let result;
      if (save) {
        await api('market-settings', 'PUT', draft);
        result = await api('clearing-summary');
      } else { result = await api('clearing-preview', 'POST', draft); }
      setSummary(result); setPreview(!save); setDirty(!save);
      if (save) setDraft(result.settings);
      setNotice(save ? 'Market settings saved.' : 'Preview updated. Save to use these settings for the community.');
    } catch (error) { setError(error.message); }
    finally { setBusy(false); }
  }

  async function joined(member) {
    setShowSignup(false); setMemberId(member.id);
    try { localStorage.setItem('gridlink-member', member.id); } catch { /* Selection works without local storage. */ }
    setBusy(true);
    try {
      setSummary(await api(preview ? 'clearing-preview' : 'clearing-summary', preview ? 'POST' : 'GET', preview ? summary.settings : undefined));
      setNotice(`${member.name} has joined the community.`);
    } catch (error) { setError(error.message); }
    finally { setBusy(false); }
  }

  const totals = summary?.totals;
  const selected = summary?.participants.find((member) => member.id === memberId);
  const change = (key, value) => { setDraft({ ...draft, [key]: value }); setDirty(true); setNotice(''); };
  const start = summary && new Date(summary.interval_start);
  const time = (date) => date.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
  const interval = start ? `${time(start)}–${time(new Date(start.getTime() + 15 * 60000))}` : '15-minute interval';

  return <>
    <header className="site-header">
      <a className="brand" href="#overview" aria-label="GridLink home"><span className="brand-mark">GL</span><span>gridlink<span className="brand-period">.</span></span></a>
      <nav aria-label="Main navigation"><a href="#overview">Overview</a><a href="#community">Community</a><a href="#pricing">Market settings</a><a href="#battery">Battery simulator</a></nav>
      <button className="button primary" onClick={() => setShowSignup(true)} disabled={!summary || busy}>Join community<Arrow diagonal /></button>
    </header>
    <main id="overview">
      <section className="hero dark">
        <div className="hero-top"><p className="eyebrow">COMMUNITY ENERGY / 001</p><span className="status"><span className="status-dot" />Simulation</span></div>
        <div className="hero-body"><div><h1>Your neighbourhood.<br />Your energy.</h1><p className="hero-copy">Buy solar from the people around you.<br />Keep more of its value in your community.</p><a className="text-link" href="#community">See the community<Arrow diagonal /></a></div><SolarArray /></div>
        <div className="market-heading"><span className="eyebrow">THE CURRENT MARKET</span><span className="muted">{interval} · {preview ? 'Unsaved preview' : 'Estimated 15-minute interval'}</span></div>
        {summary ? <div className="rate-grid"><Rate label="GRID IMPORT" value={summary.settings.grid_buy} note="The standard buying tariff" /><Rate label="GRID EXPORT" value={summary.settings.grid_sell} note="The standard selling tariff" /><Rate label="LOCAL BUYING" value={summary.rates.buyer_rate} note="Includes the buyer's transport share" /><Rate label="LOCAL SELLING" value={summary.rates.seller_rate} note="After the seller's transport share" /></div> : <div className="loading" role="status">{error ? 'The market is unavailable.' : 'Connecting to your community…'}</div>}
      </section>

      <div className="messages" aria-live="polite">{error && <div className="error global-error" role="alert">{error}<button className="button" onClick={summary ? () => setError('') : refresh} disabled={busy}>{summary ? 'Dismiss' : 'Try again'}</button></div>}{notice && <p className="notice">{notice}</p>}{preview && !notice && <p className="notice">You are viewing an unsaved pricing preview.</p>}</div>

      {summary && <>
        <section className="savings-band" aria-label="Community savings"><div><p className="eyebrow">VALUE KEPT IN THE COMMUNITY</p><h2>{money(totals.benefit)}<span>saved this interval</span></h2></div><p>{amount(totals.local_traded_kwh)} kWh traded locally.<br />{summary.participants.length} members sharing the benefit.</p><a className="circle-link" href="#ledger" aria-label="View member bill comparison"><Arrow diagonal /></a></section>

        <section className="community light" id="community">
          <div className="section-heading"><div><p className="eyebrow">01 / ENERGY FLOW</p><h2>Solar, closer to home.</h2></div><button className="button outline" onClick={refresh} disabled={busy || dirty}>{busy ? 'Updating…' : 'Refresh market'}<svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M20 10a8 8 0 1 0-2 8M20 4v6h-6" /></svg></button></div>
          <p className="section-copy">Solar powers each producer's own demand first. The community shares the surplus; the grid covers any gap.</p>
          {!summary.trade_enabled && <p className="trade-warning" role="status">{summary.trade_note}</p>}
          <div className="flow-grid">
            <article className="flow-main"><div className="panel-top"><h3>This 15-minute interval</h3><span className="small-tag">ESTIMATED</span></div>
              <div className="flow-diagram"><div className="flow-node"><span className="node-code">PV</span><p>Solar produced</p><strong>{amount(totals.generation_kwh)}<small>kWh</small></strong></div><div className="flow-connector"><span>{amount(totals.self_consumed_kwh)} kWh used<br />by producers</span><Arrow /></div><div className="flow-node"><span className="node-code">GL</span><p>Shared locally</p><strong>{amount(totals.local_traded_kwh)}<small>kWh</small></strong></div><div className="flow-connector"><span>{percent(totals.local_coverage)} of remaining<br />demand covered</span><Arrow /></div><div className="flow-node"><span className="node-code">kW</span><p>Community demand</p><strong>{amount(totals.load_kwh)}<small>kWh</small></strong></div></div>
              <div className="flow-footer"><span>From the grid <b>{amount(totals.grid_import_kwh)} kWh</b></span><span>Exported to the grid <b>{amount(totals.grid_export_kwh)} kWh</b></span><span>Transport collected <b>{money(totals.transport_collected, 4)}</b></span></div>
            </article>
            <article className="bill-panel"><p className="eyebrow">COMMUNITY BILL</p><h3>A smaller net bill.</h3><div className="bill-line"><span>Standard grid</span><span>{money(totals.benchmark_bill)}</span></div><div className="bill-bar"><span style={{ width: '100%' }} /></div><div className="bill-line"><span>With local sharing</span><span>{money(totals.optimized_bill)}</span></div><div className="bill-bar local"><span style={{ width: `${totals.benchmark_bill > 0 && totals.optimized_bill >= 0 ? Math.max(2, totals.optimized_bill / totals.benchmark_bill * 100) : 100}%` }} /></div><p className="form-note">Net cost after export earnings. Negative bills mean earnings. Transport is included.</p></article>
          </div>

          <div className="ledger-heading" id="ledger"><div><p className="eyebrow">02 / COMMUNITY LEDGER</p><h2>Everyone's share.</h2></div><span className="muted">{summary.participants.length} members · EUR per interval</span></div>
          {selected && <article className="personal-bill"><div><span className="eyebrow">YOUR PLACE IN THE COMMUNITY</span><h3>{selected.name}</h3></div><p>Grid benchmark <span>{money(selected.benchmark_bill)}</span></p><p>With GridLink <span>{money(selected.optimized_bill)}</span></p><p>Your benefit <span>{money(selected.benefit)}</span></p></article>}
          <div className="table-scroll"><table><caption className="sr-only">Estimated member energy and bills for the current 15-minute interval</caption><thead><tr><th scope="col">Member</th><th scope="col">Role</th><th scope="col">Local energy</th><th scope="col">Grid bill</th><th scope="col">GridLink bill</th><th scope="col">Benefit</th></tr></thead><tbody>{summary.participants.map((member) => <tr key={member.id} className={member.id === memberId ? 'selected-row' : ''}><th scope="row"><button className="member-button" onClick={() => { setMemberId(member.id); try { localStorage.setItem('gridlink-member', member.id); } catch { /* Optional selection persistence. */ } }}><span className="member-avatar">{member.name.slice(0, 2).toUpperCase()}</span>{member.name}{member.id === memberId && <span className="you-tag">selected</span>}</button></th><td><span className="role-label">{member.type === 'prosumer' ? 'Prosumer' : 'Consumer'}</span></td><td>{amount(member.local_sold_kwh || member.local_bought_kwh)} kWh <span className="muted">{member.local_sold_kwh > 0 ? 'sold' : member.local_bought_kwh > 0 ? 'bought' : ''}</span></td><td>{money(member.benchmark_bill)}</td><td>{money(member.optimized_bill)}</td><td>+{money(member.benefit)}</td></tr>)}</tbody></table>{!summary.participants.length && <p className="empty">The community is empty. Join to run the first interval.</p>}</div>
          <p className="ledger-note">Select a member to see their bill above. This is a shared demo; six example members are included when the local database is created.</p>
          <div className="join-row"><p>Producing solar? Buying electricity?<br />There's room for both.</p><button className="button black" onClick={() => setShowSignup(true)} disabled={busy}>Join community<Arrow diagonal /></button></div>
        </section>

        <section className="pricing dark" id="pricing"><div className="section-heading"><div><p className="eyebrow">03 / MARKET SETTINGS</p><h2>Set the terms.</h2></div><span className="small-tag">{dirty ? 'UNSAVED CHANGES' : 'SAVED SETTINGS'}</span></div>
          <div className="pricing-grid"><div className="pricing-explanation"><h3>A price between<br />buying and selling.</h3><p>The price weight sets how much of the gap between grid tariffs goes to the seller. At 0.60, the clearing price sits 60% of the way from the export tariff to the import tariff.</p><div className="formula"><span>Clearing price</span><p>Export + weight × (import − export)</p><strong>{money(summary.rates.clearing_price, 4)} <small>/ kWh</small></strong></div><p>Transport is charged once per traded kWh. The buyer pays their share on top of the clearing price. The seller's share comes out of their earnings.</p><dl className="fee-breakdown"><div><dt>Buyer pays transport</dt><dd>{money(summary.rates.buyer_transport_fee, 4)} / kWh</dd></div><div><dt>Seller pays transport</dt><dd>{money(summary.rates.seller_transport_fee, 4)} / kWh</dd></div></dl><p className="form-note">These are sample tariffs for a simulation. Settings apply to the shared community. Solar output is capacity × the output factor.</p></div>
          <form className="settings-form" onSubmit={(event) => applySettings(event, true)}><fieldset disabled={busy}>
            <div className="input-pair"><label>Grid import (€ / kWh)<input type="number" min="0" max="10" step="0.001" required value={draft.grid_buy} onChange={(event) => change('grid_buy', event.target.value === '' ? '' : Number(event.target.value))} /></label><label>Grid export (€ / kWh)<input type="number" min="0" max="10" step="0.001" required value={draft.grid_sell} onChange={(event) => change('grid_sell', event.target.value === '' ? '' : Number(event.target.value))} /></label></div>
            <label htmlFor="price-weight" className="range-label">Price weight <output>{Number(draft.price_weight).toFixed(2)}</output></label><input id="price-weight" type="range" min="0" max="1" step="0.01" value={draft.price_weight} onChange={(event) => change('price_weight', Number(event.target.value))} /><div className="range-ends"><span>Closer to grid export</span><span>Closer to grid import</span></div>
            <label htmlFor="transport">Transport fee (€ / kWh)</label><input id="transport" type="number" min="0" max="10" step="0.001" required value={draft.transport_fee} onChange={(event) => change('transport_fee', event.target.value === '' ? '' : Number(event.target.value))} />
            <label htmlFor="transport-share" className="range-label">Buyer transport share <output>{percent(draft.buyer_transport_share)}</output></label><input id="transport-share" type="range" min="0" max="1" step="0.01" value={draft.buyer_transport_share} onChange={(event) => change('buyer_transport_share', Number(event.target.value))} /><div className="range-ends"><span>Seller pays {percent(1 - draft.buyer_transport_share)}</span><span>Buyer pays {percent(draft.buyer_transport_share)}</span></div>
            <label htmlFor="solar-factor" className="range-label">Solar output factor <output>{percent(draft.solar_yield_factor)}</output></label><input id="solar-factor" type="range" min="0" max="1" step="0.01" value={draft.solar_yield_factor} onChange={(event) => change('solar_yield_factor', Number(event.target.value))} /><div className="range-ends"><span>No solar</span><span>Full rated output</span></div>
            <div className="settings-actions"><button className="button primary" type="submit" disabled={!dirty}>{busy ? 'Updating…' : 'Save settings'}<Arrow /></button><button className="button" type="button" disabled={!dirty} onClick={(event) => { if (event.currentTarget.form.reportValidity()) applySettings(event, false); }}>Preview</button><button className="text-button" type="button" disabled={!dirty} onClick={refresh}>Discard</button></div>
            <p className="form-note">Preview recalculates the dashboard. Save keeps the settings after a restart.</p>
          </fieldset></form></div>
        </section>
      </>}
      <BatteryPlanner api={api} />
    </main>
    <footer><a className="brand" href="#overview">gridlink.</a><p>Community energy, one interval at a time.</p><span>Prototype 0.1 · {summary?.storage === 'supabase' ? 'Supabase storage' : 'Local storage'}</span></footer>
    {showSignup && <Signup onClose={() => setShowSignup(false)} onJoined={joined} />}
  </>;
}
