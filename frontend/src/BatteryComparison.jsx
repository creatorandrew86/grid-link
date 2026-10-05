import { useEffect, useState } from 'react';

const number = (v, digits = 1) => Number(v).toLocaleString('en-GB', { maximumFractionDigits: digits });
const ron = v => `${number(v, 0)} RON`;
const payback = v => v == null ? 'Not recovered in service life' : `${number(v)} years`;

export default function BatteryComparison({ result, stale = false, compact = false }) {
  const [selection, setSelection] = useState(result.best_design_index ?? 0);
  useEffect(() => { setSelection(result.best_design_index ?? 0); }, [result]);
  const chosen = result?.designs?.[selection];
  const finance = chosen?.projections?.base;
  const chosenAllocation = chosen?.member_allocations?.[result?.funding_rule];
  const best = result.best_design_index;
  const recommended = best != null ? result.designs[best] : null;
  return (
    <div className="community-battery-results">
        <h3>{result.community?.name}: {result.includes_joining_member ? "after you join" : "current community"}</h3>
        <p className="small-tag">{result.source === 'planning' ? 'ILLUSTRATIVE SCENARIO' : 'MEASURED INPUTS / MODELLED RETURNS'}</p>
        {stale && <p className="notice">Inputs changed. Compare again to update these results.</p>}
        {result.message && <p className="muted">{result.message}</p>}
        {result.input_sources && <div className="planning-assumption"><p>Energy data: {result.input_sources.energy}.</p><p>Battery quotes: {result.input_sources.battery} ({result.input_sources.quote_date}).</p><p>Technical and financial assumptions: {result.input_sources.assumptions}.</p></div>}
        {result.coverage.replayed_days > 0 && <p className="muted">{result.coverage.replayed_days} complete days replayed · {new Date(result.coverage.from).toLocaleDateString('en-GB')} to {new Date(result.coverage.to).toLocaleDateString('en-GB')}</p>}
        {result.status === 'limited_history' && <p className="notice">Historical replay savings are available. Annual ROI and payback stay unavailable until 30 complete measured days are recorded.</p>}
        {best != null && <div className="battery-best-option">
          <p className="eyebrow">{result.purchase_recommended ? 'BEST OPTION BY NPV' : 'BEST COMPARED BATTERY / NO PURCHASE PREFERRED'}</p>
          <strong>{recommended.design.chemistry} / {recommended.design.capacity_kwh} kWh / {number(recommended.design.power_kw)} kW</strong>
          <div className="battery-recommendation-metrics">
            <p>Cash ROI<strong>{number(recommended.projections.base.roi_pct)}% / {recommended.projections.base.years} years</strong></p>
            <p>Payback<strong>{payback(recommended.projections.base.payback_years)}</strong></p>
            <p>NPV<strong>{ron(recommended.projections.base.npv_ron)}</strong></p>
            <p>Your contribution<strong>{recommended.member_allocations[result.funding_rule].contribution_ron == null ? 'Needs member readings' : ron(recommended.member_allocations[result.funding_rule].contribution_ron)}</strong></p>
          </div>
          {!result.purchase_recommended && <p>No compared battery has positive NPV under these assumptions. Keeping no battery is financially preferable.</p>}
          <p className="form-note">Best means the highest projected NPV among the compared options, using the selected costs and constraints.</p>
        </div>}
        {!!result.designs.length && <details className="battery-size-options" open={!compact}><summary>Compare all {result.designs.length} battery options, contributions and projections</summary>
        {!!result.designs.length && <div className="table-scroll"><table className="community-battery-table"><caption className="sr-only">Community battery investment comparison in RON</caption>
          <thead><tr><th>Battery</th><th>Installed cost</th><th>Your share</th><th>Sample cash savings</th><th>Year 1 net savings</th><th>Payback</th><th>Cash ROI</th><th>NPV</th></tr></thead>
          <tbody>{result.designs.map((d, i) => <tr key={`${d.design.chemistry}-${d.design.capacity_kwh}`} className={selection === i ? 'selected-row' : ''}>
            <th scope="row"><button type="button" className="text-button" onClick={() => setSelection(i)}>{d.design.chemistry} · {d.design.capacity_kwh} kWh / {number(d.design.power_kw)} kW</button>{i === best && <span className="you-tag">Highest NPV</span>}</th>
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
          <h3>{chosen.design.chemistry} · {chosen.design.capacity_kwh} kWh: {result.community?.name} projection</h3>
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
      </details>}
    </div>
  );
}
