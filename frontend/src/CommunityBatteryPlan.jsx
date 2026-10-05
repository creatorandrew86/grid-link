import { useEffect, useState } from 'react';
import { api } from './apiClient';

const presets = [
  { chemistry: 'LFP', cost: 1000, efficiency: .92, usable_fraction: .9, service_years: 12 },
  { chemistry: 'NMC', cost: 1200, efficiency: .9, usable_fraction: .85, service_years: 10 },
  { chemistry: 'Lead-acid', cost: 700, efficiency: .8, usable_fraction: .5, service_years: 5 },
];
const number = (v, digits = 1) => Number(v).toLocaleString('en-GB', { maximumFractionDigits: digits });
const ron = v => `${number(v, 0)} RON`;
const payback = v => v == null ? 'Not recovered in service life' : `${number(v)} years`;

export default function CommunityBatteryPlan({ memberId, onSwitched }) {
  const [context, setContext] = useState(null);
  const [source, setSource] = useState('measured');
  const [confirmed, setConfirmed] = useState(false);
  const [fundingRule, setFundingRule] = useState('equal_share');
  const [destination, setDestination] = useState(null);
  const [types, setTypes] = useState(presets);
  const [sizes, setSizes] = useState('5, 10, 20');
  const [fixedCost, setFixedCost] = useState(1500);
  const [maintenance, setMaintenance] = useState(100);
  const [horizon, setHorizon] = useState(10);
  const [discount, setDiscount] = useState(6);
  const [fade, setFade] = useState(2);
  const [powerRatio, setPowerRatio] = useState(.5);
  const [importLimit, setImportLimit] = useState(100);
  const [exportLimit, setExportLimit] = useState(100);
  const [wear, setWear] = useState(.15);
  const [result, setResult] = useState(null);
  const [selection, setSelection] = useState(0);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [stale, setStale] = useState(false);

  useEffect(() => {
    let active = true;
    api('community-battery').then(data => { if (active) setContext(data); })
      .catch(err => { if (active) setError(err.message); });
    return () => { active = false; };
  }, [memberId]);

  const change = (setter, value) => { setter(value); setStale(true); };
  const updateType = (index, key, value) => {
    setTypes(current => current.map((t, i) => i === index ? { ...t, [key]: Number(value) } : t));
    setStale(true);
  };

  async function compare(event) {
    event.preventDefault();
    setError(''); setNotice(''); setBusy(true);
    try {
      const capacities = [...new Set(sizes.split(',').map(s => Number(s.trim())))];
      if (!capacities.length || capacities.length > 3 || capacities.some(c => !Number.isFinite(c) || c <= 0 || c > 1000)) {
        throw new Error('Enter one to three battery sizes between 0 and 1000 kWh, separated by commas.');
      }
      const designs = types.flatMap(t => capacities.map(capacity => ({
        chemistry: t.chemistry, capacity_kwh: capacity, power_kw: capacity * Number(powerRatio),
        installed_cost_ron: capacity * t.cost + Number(fixedCost), efficiency: t.efficiency,
        usable_fraction: t.usable_fraction, service_years: t.service_years, annual_fade: Number(fade) / 100,
        annual_maintenance_ron: Number(maintenance),
      })));
      const data = await api('community-battery/compare', 'POST', {
        source, shared_meter_confirmed: confirmed, funding_rule: fundingRule, designs, horizon_years: Number(horizon),
        discount_rate: Number(discount) / 100, connection_import_kw: Number(importLimit),
        connection_export_kw: Number(exportLimit), dispatch_wear_ron_per_kwh: Number(wear),
      });
      setResult(data); setSelection(0); setStale(false);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  async function saveInterest(interested) {
    setBusy(true); setError(''); setNotice('');
    try {
      await api('community-battery/interest', 'PUT', { interested });
      setContext(await api('community-battery'));
      setNotice('Your preference is saved. No payment has been committed.');
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  async function acceptSwitch(target_community_id) {
    setBusy(true); setError(''); setNotice('');
    try {
      const data = await api('community-battery/switch', 'POST', { target_community_id });
      onSwitched(data.user);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  const chosen = result?.designs?.[selection];
  const finance = chosen?.projections?.base;
  const chosenAllocation = chosen?.member_allocations?.[result?.funding_rule];
  const best = result?.designs?.reduce((current, d, index) => d.projections &&
    (current == null || d.projections.base.npv_ron > result.designs[current].projections.base.npv_ron) ? index : current, null);

  return <section className="community-battery-plan" aria-labelledby="community-battery-title">
    <p className="eyebrow">SHARED STORAGE / COMMUNITY INVESTMENT</p>
    <h2 id="community-battery-title">A battery for your community.</h2>
    <p className="muted">Compare whole-community savings and two ways to share the cost. Member records stay private.</p>
    {error && <p className="error" role="alert">{error}</p>}
    {notice && <p className="notice" role="status">{notice}</p>}
    {!context ? <p className="muted">{error ? 'Planning is unavailable until the connection or database setup is fixed.' : 'Loading your community…'}</p> : <>
      <div className="community-battery-status">
        <div><span className="eyebrow">YOUR COMMUNITY</span><strong>{context.community.name}</strong><p className="muted">Battery plan: {context.community.battery_policy}</p></div>
        <div><span className="eyebrow">MEASURED HISTORY</span><strong>{context.coverage.complete_days} complete days</strong><p className="muted">{context.coverage.incomplete_days} incomplete days excluded. ROI needs 30 complete days.</p></div>
        <div><span className="eyebrow">SHARED FUNDING</span><strong>{context.member_count} members</strong><p className="muted">{context.interested_count} interested · {context.answered_count} answered</p></div>
      </div>

      <form onSubmit={compare} onChange={() => setStale(true)}>
        <fieldset disabled={busy}>
          <div className="input-pair">
            <label>Data used<select value={source} onChange={e => change(setSource, e.target.value)}>
              <option value="measured">My community’s measured history</option><option value="planning">Illustrative planning preview</option>
            </select></label>
            <label>Battery sizes (kWh)<input value={sizes} required onChange={e => change(setSizes, e.target.value)} placeholder="5, 10, 20" /></label>
            <label>Funding scenario<select value={fundingRule} onChange={e => change(setFundingRule, e.target.value)}>
              <option value="equal_share">Equal contribution and ownership</option><option value="consumption_share">Contribution proportional to consumption</option>
            </select></label>
          </div>
          {source === 'planning' && <div className="planning-assumption">
            <p>This preview uses your community’s entered demand and PV capacity with historical Romanian prices and weather. Demand is assumed flat; these are not your community’s measured savings.</p>
            <label className="battery-checkbox"><input type="checkbox" checked={confirmed} required onChange={e => change(setConfirmed, e.target.checked)} />Model the entire community behind one shared billing meter.</label>
          </div>}
          {source === 'measured' && context.community.meter_boundary !== 'shared_meter' && <p className="form-note">The operator must verify the shared billing meter. Separate household meters need a different settlement model.</p>}
          <details>
            <summary>Battery assumptions and installed costs</summary>
            <p className="form-note">These are editable, illustrative technology assumptions, not supplier quotes. Include equipment, inverter, installation and taxes in your cost inputs.</p>
            <div className="table-scroll"><table className="battery-quote-table"><caption className="sr-only">Editable battery technology assumptions</caption>
              <thead><tr><th>Type</th><th>Equipment RON/kWh</th><th>Efficiency</th><th>Usable fraction</th><th>Service years</th></tr></thead>
              <tbody>{types.map((t, i) => <tr key={t.chemistry}><th scope="row">{t.chemistry}</th>
                {[['cost', 1, 100000, 1], ['efficiency', .01, 1, .01], ['usable_fraction', .01, 1, .01], ['service_years', 1, 30, 1]].map(([key, min, max, step]) =>
                  <td key={key}><input aria-label={`${t.chemistry} ${key}`} type="number" min={min} max={max} step={step} required value={t[key]} onChange={e => updateType(i, key, e.target.value)} /></td>)}</tr>)}</tbody>
            </table></div>
            <div className="input-pair">
              <label>Installation and other fixed costs (RON)<input type="number" min="0" step="1" required value={fixedCost} onChange={e => change(setFixedCost, e.target.value)} /></label>
              <label>Annual maintenance (RON)<input type="number" min="0" max="100000" required value={maintenance} onChange={e => change(setMaintenance, e.target.value)} /></label>
              <label>Battery power per kWh (kW)<input type="number" min=".01" max="1" step=".01" required value={powerRatio} onChange={e => change(setPowerRatio, e.target.value)} /></label>
              <label>Annual savings fade (%)<input type="number" min="0" max="20" step=".1" required value={fade} onChange={e => change(setFade, e.target.value)} /></label>
              <label>Analysis horizon (years)<input type="number" min="1" max="30" required value={horizon} onChange={e => change(setHorizon, e.target.value)} /></label>
              <label>Discount rate (%)<input type="number" min="0" max="50" step=".1" required value={discount} onChange={e => change(setDiscount, e.target.value)} /></label>
              <label>Grid import limit (kW)<input type="number" min=".1" max="2000" step=".1" required value={importLimit} onChange={e => change(setImportLimit, e.target.value)} /></label>
              <label>Grid export limit (kW)<input type="number" min="0" max="2000" step=".1" required value={exportLimit} onChange={e => change(setExportLimit, e.target.value)} /></label>
              <label>Dispatch wear allowance (RON/kWh)<input type="number" min="0" max="10" step=".01" required value={wear} onChange={e => change(setWear, e.target.value)} /></label>
            </div>
          </details>
          <button className="button primary" type="submit">{busy ? 'Working…' : 'Compare shared batteries'}</button>
        </fieldset>
      </form>

      {result && <div className="community-battery-results">
        <p className="small-tag">{result.source === 'planning' ? 'ILLUSTRATIVE SCENARIO' : 'MEASURED INPUTS / MODELLED RETURNS'}</p>
        {stale && <p className="notice">Inputs changed. Compare again to update these results.</p>}
        {result.message && <p className="muted">{result.message}</p>}
        {result.coverage.replayed_days > 0 && <p className="muted">{result.coverage.replayed_days} complete days replayed · {new Date(result.coverage.from).toLocaleDateString('en-GB')} to {new Date(result.coverage.to).toLocaleDateString('en-GB')}</p>}
        {result.status === 'limited_history' && <p className="notice">Observed replay savings are available. Annual ROI and payback stay unavailable until 30 complete measured days are recorded.</p>}
        {best != null && <p className="form-note">Highest modelled NPV: {result.designs[best].design.chemistry} / {result.designs[best].design.capacity_kwh} kWh.{result.designs[best].projections.base.npv_ron < 0 ? ' All compared options have negative NPV under these assumptions.' : ''}</p>}
        {!!result.designs.length && <div className="table-scroll"><table className="community-battery-table"><caption className="sr-only">Community battery investment comparison in RON</caption>
          <thead><tr><th>Battery</th><th>Installed cost</th><th>Your share</th><th>Sample cash savings</th><th>Year 1 net savings</th><th>Payback</th><th>Cash ROI</th><th>NPV</th></tr></thead>
          <tbody>{result.designs.map((d, i) => <tr key={`${d.design.chemistry}-${d.design.capacity_kwh}`} className={selection === i ? 'selected-row' : ''}>
            <th scope="row"><button type="button" className="text-button" onClick={() => setSelection(i)}>{d.design.chemistry} · {d.design.capacity_kwh} kWh / {number(d.design.power_kw)} kW</button></th>
            {d.error ? <td colSpan="7">Unavailable: {d.error}</td> : <><td>{ron(d.design.installed_cost_ron)}</td><td>{d.member_allocations[result.funding_rule].contribution_ron == null ? 'Needs member readings' : ron(d.member_allocations[result.funding_rule].contribution_ron)}</td><td>{ron(d.sample_cash_saving_ron)}</td>
              <td>{d.projections ? ron(d.projections.base.first_year_net_saving_ron) : '—'}</td><td>{d.projections ? payback(d.projections.base.payback_years) : '—'}</td>
              <td>{d.projections ? `${number(d.projections.base.roi_pct)}% / ${d.projections.base.years} years` : '—'}</td><td>{d.projections ? ron(d.projections.base.npv_ron) : '—'}</td></>}
          </tr>)}</tbody>
        </table></div>}
        {chosen?.member_allocations && <div className="funding-comparison">
          <h3>Which contribution is fairer?</h3>
          <div className="table-scroll"><table><caption>Your funding options for {chosen.design.chemistry} / {chosen.design.capacity_kwh} kWh</caption><thead><tr><th>Rule</th><th>Your ownership share</th><th>Your contribution</th><th>Your allocated year 1 savings</th></tr></thead>
            <tbody>{Object.entries(chosen.member_allocations).map(([rule, a]) => <tr key={rule}><th scope="row">{rule === 'equal_share' ? 'Equal shares' : 'Consumption shares'}</th><td>{a.share == null ? 'Needs member readings' : `${number(a.share * 100)}%`}</td><td>{a.contribution_ron == null ? '—' : ron(a.contribution_ron)}</td><td>{a.first_year_saving_ron == null ? '—' : ron(a.first_year_saving_ron)}</td></tr>)}</tbody>
          </table></div>
          <p className="muted">Equal shares are simple and fit equal ownership and similar usage. Consumption shares ask higher-use members to pay more, which can be fairer when demand differs, but gross consumption does not measure each member’s actual battery benefit.</p>
          <p className="muted">Both scenarios allocate savings using the same shares as the costs, so they have the same percentage return and payback. The group must agree on ownership, savings, exits and contributions before purchase. Existing owners’ shares should stay fixed after purchase rather than change with each new reading.</p>
          {chosen.member_allocations.consumption_share.share == null && <p className="form-note">Consumption allocation needs complete readings for every current member. No missing share is guessed.</p>}
        </div>}
        {finance && <div className="battery-projection">
          <h3>{chosen.design.chemistry} · {chosen.design.capacity_kwh} kWh: your community’s projection</h3>
          <p className="muted">Your allocated first-year net savings: {chosenAllocation?.first_year_saving_ron == null ? 'unavailable until member readings are complete' : ron(chosenAllocation.first_year_saving_ron)}. Funding scenario: {result.funding_rule === 'equal_share' ? 'equal shares' : 'consumption shares'}.</p>
          <div className="projection-bars" role="img" aria-label={`Projected cumulative community cash flow over ${finance.years} years`}>
            {finance.timeline.map(row => <div key={row.year}><span>Year {row.year}</span><div><i style={{ width: `${Math.max(1, Math.abs(row.cumulative_ron) / Math.max(...finance.timeline.map(r => Math.abs(r.cumulative_ron))) * 100)}%`, background: row.cumulative_ron < 0 ? '#777' : 'var(--yellow)' }} /></div><strong>{ron(row.cumulative_ron)}</strong></div>)}
          </div>
          <div className="table-scroll"><table><caption>Savings sensitivity for the selected battery</caption><thead><tr><th>Scenario</th><th>Year 1 net savings</th><th>Payback</th><th>NPV</th></tr></thead>
            <tbody>{Object.entries(chosen.projections).map(([name, p]) => <tr key={name}><th scope="row">{name}</th><td>{ron(p.first_year_net_saving_ron)}</td><td>{payback(p.payback_years)}</td><td>{ron(p.npv_ron)}</td></tr>)}</tbody>
          </table></div>
        </div>}
        {!!result.notes?.length && <details><summary>How to read these estimates</summary><ul>{result.notes.map(note => <li key={note}>{note}</li>)}</ul>
          <p><a href="https://sam.nrel.gov/battery-storage.html" target="_blank" rel="noreferrer">NREL SAM battery modelling</a> · <a href="https://sam.nrel.gov/financial-models.html" target="_blank" rel="noreferrer">Financial metrics reference</a></p>
        </details>}
      </div>}

      <div className="battery-community-choice">
        <h3>Would you fund a shared battery?</h3>
        <p className="muted">Your current preference: {context.your_interest == null ? 'Not answered' : context.your_interest ? 'Interested' : 'Not interested'}. The community must agree on the purchase before anyone pays.</p>
        <div className="battery-preference-actions"><button className="button primary" disabled={busy} onClick={() => saveInterest(true)}>I’m interested</button><button className="button outline" disabled={busy} onClick={() => saveInterest(false)}>Not interested</button></div>
        {context.your_interest && <>
          <h3>Find a community planning shared storage</h3>
          <p className="muted">These communities want shared storage and have opened admissions in your network zone. Review a suggestion, then choose whether to switch. Your home and meter stay where they are; joining does not commit a payment.</p>
          {context.candidates.length ? context.candidates.map(c => <div className="battery-transfer-option" key={c.id}><div><strong>{c.name}</strong><p className="muted">Battery plan: {c.battery_policy} · eligible for your meter</p></div><button className="button outline" disabled={busy} onClick={() => setDestination(c)}>Review suggestion</button></div>) : <p className="muted">No eligible community is accepting members yet. Your operator can review communities and your meter’s eligibility.</p>}
          {destination && <div className="planning-assumption" role="region" aria-label="Review community switch"><h3>Switch to {destination.name}?</h3><p>You will leave {context.community.name} and join {destination.name}, which is planning shared storage. The server checks admissions and meter eligibility again before moving your membership.</p><div className="battery-preference-actions"><button className="button primary" disabled={busy} onClick={() => acceptSwitch(destination.id)}>Accept and switch community</button><button className="button outline" disabled={busy} onClick={() => setDestination(null)}>Stay in my community</button></div></div>}
        </>}
      </div>
    </>}
  </section>;
}
