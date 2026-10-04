import { useEffect, useState } from 'react';

const defaults = {
  day: '2026-07-30', daily_load_kwh: 50, load_profile: 'evening', solar_kwp: 20, pv_performance_ratio: .8,
  capacity_kwh: 20, charge_kw: 5, discharge_kw: 5, round_trip_efficiency: .9, reserve_fraction: .1,
  initial_soc_fraction: .1, max_soc_fraction: .9, wear_ron_per_kwh: .15, import_fee_ron_per_kwh: .5879032,
  vat_fraction: .21, export_price_factor: 1, export_fee_ron_per_kwh: .05,
  grid_import_kw: 100, grid_export_kw: 100, allow_battery_export: false,
};
const number = (v, digits = 2) => Number(v).toLocaleString('en-GB', { maximumFractionDigits: digits });
const ron = (v) => `${number(v)} RON`;
const titles = { baseline: 'No battery', night: 'Night-only', optimised: 'Optimised', calendar: 'Calendar estimate', local: 'Local weather', weather: 'Local + coastal weather' };

function Chart({ rows, series, title, unit }) {
  const [hover, setHover] = useState(null);
  const width = 760, height = 230, left = 58, right = 16, top = 14, bottom = 38;
  const values = series.flatMap(s => rows.map(r => Number(r[s.key])));
  const min = Math.min(0, ...values), max = Math.max(1e-3, ...values), span = max - min || 1;
  const x = i => left + i / Math.max(1, rows.length - 1) * (width - left - right);
  const y = value => top + (max - value) / span * (height - top - bottom);
  return <article className="battery-chart">
    <div className="panel-top"><h3>{title}</h3><span className="muted">{unit}</span></div>
    <div className="battery-plot"><svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${title}. Exact values are available in the hourly schedule below.`}
      onMouseMove={event => { const box = event.currentTarget.getBoundingClientRect(); setHover(Math.max(0, Math.min(rows.length - 1, Math.round(((event.clientX - box.left) / box.width * width - left) / (width - left - right) * (rows.length - 1))))); }} onMouseLeave={() => setHover(null)}>
      {[0, .5, 1].map(t => <g key={t}><line x1={left} x2={width - right} y1={y(min + span * t)} y2={y(min + span * t)} stroke="#4b4b4b" /><text x={left - 10} y={y(min + span * t) + 4} textAnchor="end">{number(min + span * t)}</text></g>)}
      {rows.map((row, i) => (i % 4 === 0 || i === rows.length - 1) && <text key={row.utc} x={x(i)} y={height - 12} textAnchor="middle">{row.bucharest_time.slice(11, 16)}</text>)}
      {series.map(s => <polyline key={s.key} fill="none" stroke={s.color} strokeWidth="2" strokeDasharray={s.dash} points={rows.map((r, i) => `${x(i)},${y(r[s.key])}`).join(' ')} />)}
      {hover !== null && <line x1={x(hover)} x2={x(hover)} y1={top} y2={height - bottom} stroke="#afafaf" strokeDasharray="3 4" />}
    </svg></div>
    <div className="chart-legend">{series.map(s => <span key={s.key}><i style={{ borderColor: s.color, borderTopStyle: s.dash ? 'dashed' : 'solid' }} />{s.label}{hover !== null && `: ${number(rows[hover][s.key])} ${unit}`}</span>)}</div>
  </article>;
}

export default function BatteryPlanner({ api }) {
  const [config, setConfig] = useState(defaults);
  const [dataset, setDataset] = useState(null);
  const [result, setResult] = useState(null);
  const [selected, setSelected] = useState('optimised');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [outlook, setOutlook] = useState(null);
  const [outlookBusy, setOutlookBusy] = useState(false);
  const [outlookError, setOutlookError] = useState('');
  useEffect(() => {
    let active = true;
    Promise.all([api('battery/dataset'), api('battery/simulate', 'POST', defaults)])
      .then(([data, replay]) => { if (active) { setDataset(data); setResult(replay); } })
      .catch(error => { if (active) setError(error.message); });
    return () => { active = false; };
  }, []);
  const change = (key, value) => setConfig(c => ({ ...c, [key]: value }));
  const stale = result && Object.entries(config).some(([key, value]) => value !== result.config[key]);
  async function run(event) {
    event.preventDefault(); setBusy(true); setError('');
    try { const replay = await api('battery/simulate', 'POST', config); setResult(replay); if (!replay.strategies[selected]) setSelected('optimised'); }
    catch (error) { setError(error.message); }
    finally { setBusy(false); }
  }
  async function loadOutlook() {
    setOutlookBusy(true); setOutlookError('');
    try { setOutlook(await api('battery/weather-outlook')); }
    catch (error) { setOutlookError(error.message); }
    finally { setOutlookBusy(false); }
  }
  function field(key, label, min = 0, max = 1000, step = .1, scale = 1) {
    return <label key={key}>{label}<input name={key} type="number" required min={min} max={max} step={step}
      value={config[key] === '' ? '' : Number((config[key] * scale).toFixed(7))}
      onChange={event => change(key, event.target.value === '' ? '' : Number(event.target.value) / scale)} /></label>;
  }
  const strategy = result?.strategies[selected];
  const rows = strategy?.rows.map((row, i) => ({ ...row,
    calendar_estimate: result.weather_experiment.calendar_prices?.[i] ?? row.price_lei_kwh,
    weather_estimate: result.weather_experiment.weather_prices?.[i] ?? row.price_lei_kwh,
  }));
  const experiment = result?.weather_experiment;

  return <section id="battery" className="battery-section light" aria-labelledby="battery-title">
    <div className="section-heading"><div><p className="eyebrow">04 / BATTERY SIMULATOR</p><h2 id="battery-title">Store energy for the right hours.</h2></div><span className="small-tag">HISTORICAL REPLAY / RON</span></div>
    <p className="section-copy">Compare schedules using real Romanian prices and Bucharest weather. Set an assumed demand, solar system and battery for one shared billing meter.</p>
    <div className="battery-presets" role="group" aria-label="Example battery scenarios">
      <button type="button" className="button outline" disabled={busy} onClick={() => setConfig({ ...defaults, day: '2026-01-20', solar_kwp: 5 })}>Winter demand</button>
      <button type="button" className="button outline" disabled={busy} onClick={() => setConfig({ ...defaults })}>Summer solar</button>
      <button type="button" className="button outline" disabled={busy} onClick={() => setConfig({ ...defaults, day: '2026-09-01', daily_load_kwh: 15, solar_kwp: 30, allow_battery_export: true })}>Surplus for export</button>
    </div>
    <div className="battery-layout">
      <form onSubmit={run} className="battery-form"><fieldset disabled={busy}>
        <label>Research date<select name="day" required value={config.day} onChange={e => change('day', e.target.value)}>
          {(dataset?.days || [config.day]).map(day => <option key={day} value={day}>{day}</option>)}</select></label>
        <p className="form-note">120 selected days across January, April, July and September 2026. Each replay starts fresh.</p>
        <div className="input-pair">{field('daily_load_kwh', 'Daily demand (kWh)')}{field('solar_kwp', 'Solar capacity (kWp)')}</div>
        <label>Demand profile<select name="load_profile" value={config.load_profile} onChange={e => change('load_profile', e.target.value)}><option value="evening">Evening peak</option><option value="daytime">Daytime peak</option><option value="flat">Flat demand</option></select></label>
        <div className="input-pair">{field('capacity_kwh', 'Battery capacity (kWh)')}{field('round_trip_efficiency', 'Round-trip efficiency (%)', 1, 100, 1, 100)}</div>
        <div className="input-pair">{field('charge_kw', 'Charge limit (kW)')}{field('discharge_kw', 'Discharge limit (kW)')}</div>
        <label className="battery-checkbox"><input type="checkbox" name="allow_battery_export" checked={config.allow_battery_export} onChange={e => change('allow_battery_export', e.target.checked)} />Allow battery discharge for grid exports</label>
        <p className="form-note">Enable to test selling stored energy. Export revenue uses the illustrative contract below.</p>
        <details><summary>Battery reserve and contract assumptions</summary>
          <div className="input-pair">{field('reserve_fraction', 'Minimum charge (%)', 0, 100, 1, 100)}{field('max_soc_fraction', 'Maximum charge (%)', 0, 100, 1, 100)}</div>
          {field('initial_soc_fraction', 'Starting and ending charge (%)', 0, 100, 1, 100)}
          <div className="input-pair">{field('pv_performance_ratio', 'PV performance ratio (%)', 1, 100, 1, 100)}{field('wear_ron_per_kwh', 'Wear (RON / discharged kWh)', 0, 10, .01)}</div>
          {field('import_fee_ron_per_kwh', 'Import charges before VAT (RON / kWh)', 0, 10, .0000001)}
          {field('vat_fraction', 'Import VAT (%)', 0, 100, 1, 100)}
          <div className="input-pair">{field('export_price_factor', 'Wholesale export price paid (%)', 0, 100, 1, 100)}{field('export_fee_ron_per_kwh', 'Export deduction (RON / kWh)', 0, 10, .01)}</div>
          <div className="input-pair">{field('grid_import_kw', 'Grid import limit (kW)', .1, 2000)}{field('grid_export_kw', 'Grid export limit (kW)', 0, 2000)}</div>
          <p className="form-note">Import = (OPCOM price + charges) × (1 + VAT). Export = OPCOM price × paid share − deduction. Replace these assumptions with your actual contract. Community price weight and transport splits are separate.</p>
        </details>
        <button type="submit" className="button black">{busy ? 'Calculating…' : 'Run comparison'}</button>
        {stale && <p role="status" className="form-note">Settings changed. Results below still show {result.config.day}; run again to update them.</p>}
        {error && <p className="battery-error" role="alert">{error}</p>}
      </fieldset></form>
      <div className="battery-results" aria-live="polite">
        {!result && <p role="status">{error ? 'Simulation unavailable. Run the comparison to retry.' : 'Loading the first comparison…'}</p>}
        {result && <>
          <div className="battery-stats"><div><p className="eyebrow">OPTIMISED SAVINGS AFTER WEAR</p><strong>{ron(result.strategies.optimised.savings_ron)}</strong><p>for {result.config.day}</p></div><div><p className="eyebrow">GRID IMPORTS</p><strong>{number(result.strategies.optimised.grid_import_kwh)} kWh</strong><p>{number(result.strategies.baseline.grid_import_kwh)} kWh without storage</p></div></div>
          <div className="table-scroll"><table className="strategy-table"><caption className="sr-only">Daily strategy costs including battery wear</caption><thead><tr><th>Strategy</th><th>Energy bill</th><th>Wear</th><th>Total</th><th>Savings</th></tr></thead><tbody>
            {Object.entries(result.strategies).map(([key, s]) => <tr key={key} className={selected === key ? 'selected-row' : ''}><th scope="row"><button type="button" aria-pressed={selected === key} onClick={() => setSelected(key)}>{titles[key]}</button></th><td>{ron(s.energy_cost_ron)}</td><td>{ron(s.wear_cost_ron)}</td><td>{ron(s.total_cost_ron)}</td><td>{ron(s.savings_ron)}</td></tr>)}
          </tbody></table></div>
          <p className="form-note">Select a strategy to inspect it. Negative bills mean net export earnings. The optimised replay knows the day's actual prices and scenario PV; it is a reference for this assumed system.</p>
          <Chart rows={rows} title="Wholesale price and experimental estimates" unit="RON / kWh" series={[
            { key: 'price_lei_kwh', label: 'Actual OPCOM', color: '#eeeeee' },
            ...(experiment.available ? [{ key: 'calendar_estimate', label: 'Calendar estimate', color: '#afafaf', dash: '5 4' }, { key: 'weather_estimate', label: 'Weather estimate', color: '#fff313', dash: '2 3' }] : []),
          ]} />
          <Chart rows={rows} title={`${titles[selected]}: hourly energy`} unit="kWh" series={[
            { key: 'load_kwh', label: 'Demand', color: '#eeeeee' }, { key: 'pv_kwh', label: 'Solar', color: '#afafaf', dash: '5 4' },
            { key: 'grid_import_kwh', label: 'Grid imports', color: '#fff313' },
          ]} />
          <Chart rows={rows} title="Battery charge" unit="kWh" series={[{ key: 'soc_kwh', label: 'Stored energy at hour end', color: '#eeeeee' }]} />
        </>}
      </div>
    </div>
    {result && <>
      <div className="battery-weather"><p className="eyebrow">LOCAL WEATHER / REGIONAL GENERATION</p><h3>Does weather improve the schedule?</h3>
        <p>Sunny conditions here and weak renewable output elsewhere may favour exports. Constanța and Tulcea represent a coastal weather proxy; they cannot establish a national energy shortage.</p>
        {experiment.available ? <div className="weather-metrics"><p>Calendar price error<span>{number(experiment.calendar_mae_ron_kwh, 3)} RON / kWh</span></p><p>Local weather price error<span>{number(experiment.local_mae_ron_kwh, 3)} RON / kWh</span></p><p>Local + coastal price error<span>{number(experiment.weather_mae_ron_kwh, 3)} RON / kWh</span></p><p>Adding coastal weather saves<span>{ron(experiment.regional_advantage_ron)}</span></p></div> : null}
        <p className="form-note">{experiment.note} {experiment.available && `Training: ${experiment.training_days} earlier data days, ending ${experiment.training_end}. A negative coastal advantage means adding regional weather made the realised result worse.`}</p>
        <button type="button" className="button outline" disabled={outlookBusy} onClick={loadOutlook}>{outlookBusy ? 'Fetching forecasts…' : 'Fetch current 48-hour weather outlook'}</button>
        {outlookError && <p role="alert" className="battery-error">{outlookError}</p>}
        {outlook && <><p className="form-note">Retrieved {new Date(outlook.retrieved_at).toLocaleString('en-GB')}. {outlook.note}</p><div className="table-scroll"><table><caption className="sr-only">Regional forecast context for the next 48 hours</caption><thead><tr><th>Forecast location</th><th>48-hour irradiation (kWh/m²)</th><th>Mean wind at 100 m (m/s)</th></tr></thead><tbody>{outlook.regions.map(r => <tr key={r.name}><th scope="row">{r.name}</th><td>{number(r.irradiation_kwh_m2)}</td><td>{number(r.mean_wind_100m_m_s)}</td></tr>)}</tbody></table></div><div className="table-scroll"><table><caption className="sr-only">Current weather forecasts and experimental wholesale price estimates</caption><thead><tr><th>Bucharest time</th><th>Local sun (W/m²)</th><th>Coastal wind proxy (%)</th><th>Calendar price</th><th>Weather price</th></tr></thead><tbody>{outlook.rows.map(r => <tr key={r.utc}><th scope="row">{r.bucharest_time.slice(0, 16).replace('T', ' ')}</th><td>{number(r.bucharest_ghi_w_m2, 0)}</td><td>{number(r.coastal_wind_proxy * 100, 0)}</td><td>{ron(r.calendar_price_estimate)} / kWh</td><td>{ron(r.weather_price_estimate)} / kWh</td></tr>)}</tbody></table></div></>}
      </div>
      <details className="hourly-details"><summary>Hourly schedule: {titles[selected]}</summary><div className="table-scroll"><table><caption className="sr-only">Hourly battery dispatch and grid exchange in kWh</caption><thead><tr><th>Bucharest hour</th><th>Charge</th><th>Discharge</th><th>Stored</th><th>Import</th><th>Export</th><th>Curtailed PV</th></tr></thead><tbody>{rows.map(r => <tr key={r.utc}><th scope="row">{r.bucharest_time.slice(11, 16)}</th><td>{number(r.charge_kwh)}</td><td>{number(r.discharge_kwh)}</td><td>{number(r.soc_kwh)}</td><td>{number(r.grid_import_kwh)}</td><td>{number(r.grid_export_kwh)}</td><td>{number(r.curtailed_kwh)}</td></tr>)}</tbody></table></div></details>
      <details className="hourly-details"><summary>Weather mismatch signals for this replay</summary><p className="form-note">Illustrative thresholds; signals do not override prices or certify shortages. Only the two coastal points are used.</p><div className="table-scroll"><table><thead><tr><th>Hour</th><th>Local surplus (kWh)</th><th>Coastal wind proxy (%)</th><th>Signal</th></tr></thead><tbody>{result.opportunities.map(r => <tr key={r.bucharest_time}><th scope="row">{r.bucharest_time.slice(11, 16)}</th><td>{number(r.local_surplus_kwh)}</td><td>{number(r.coastal_wind_proxy * 100, 0)}</td><td>{r.signal}</td></tr>)}</tbody></table></div></details>
      <p className="battery-assumptions">Hourly simulation, no equipment control. Demand profiles and PV output are estimates. All schedules preserve starting battery charge; equipment cost and real community settlement are excluded.</p>
    </>}
  </section>;
}
