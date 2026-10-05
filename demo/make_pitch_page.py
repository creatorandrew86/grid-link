"""Create a self-contained pitch page that also opens offline without fetch/network."""
import base64
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public/demo"
payload = json.loads((PUBLIC / "results.json").read_text(encoding="utf-8"))
images = {name: "data:image/png;base64," + base64.b64encode((PUBLIC / (name + ".png")).read_bytes()).decode()
          for name in ("dispatch", "sizing")}
template = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>GridLink | Hackathon demonstration</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#080808;color:#eee;font:17px/1.55 system-ui,sans-serif}main{max-width:1220px;margin:auto;padding:38px 30px}header{display:flex;justify-content:space-between;gap:20px;align-items:center}h1{font-size:clamp(32px,5vw,60px);font-weight:400;line-height:1.1}h2{font-size:28px;font-weight:400}h3{font-size:21px;font-weight:400}.muted{color:#bbb}.tag{color:#fff313;letter-spacing:.13em;font-size:12px;text-transform:uppercase}a{color:#fff313}button,select{font:inherit;background:#161616;color:#eee;border:1px solid #777;border-radius:6px;padding:12px 18px;cursor:pointer}button.active{background:#fff313;color:#111;border-color:#fff313}.controls{display:flex;gap:12px;flex-wrap:wrap;margin:26px 0}.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}.card{border:1px solid #555;border-radius:9px;padding:22px}.card strong{display:block;font-size:30px;font-weight:400}.notice{padding:18px 22px;border-left:3px solid #fff313;background:#181818}.table-scroll{overflow-x:auto}table{width:100%;border-collapse:collapse;font-size:15px}td,th{text-align:left;padding:12px;border-bottom:1px solid #444}tr.best{background:#33340a}.section{margin:40px 0;padding-top:22px;border-top:1px solid #555}.chart{width:100%;background:white;border-radius:8px}.split{display:grid;grid-template-columns:1fr 1fr;gap:24px}details{margin:20px 0}summary{cursor:pointer}.stage{padding:14px;border-bottom:1px solid #444}.hidden,[hidden]{display:none!important}.pill{background:#fff313;color:#111;display:inline-block;border-radius:5px;padding:4px 10px}.positive{color:#b3ed89}.negative{color:#ffb08a}footer{font-size:13px;margin:50px 0 20px;color:#bbb}@media(max-width:800px){.cards,.split{grid-template-columns:1fr 1fr}}@media(max-width:500px){.cards,.split{grid-template-columns:1fr}main{padding:24px 18px}header{display:block}}
</style></head><body><main>
<header><div class="tag">gridlink. / hackathon demo</div><a href="http://127.0.0.1:5173/#account" target="_blank" rel="noopener">Open live app ↗</a></header>
<h1>One community.<br>Many battery options.</h1>
<p class="muted">Automatically compare shared battery sizes, contributions and eligible communities.</p>
<div class="notice"><strong>Published-data replay, not live Romanian community measurements.</strong><br>Measured German household donor days + real historical Romanian prices + modelled solar. Communities, shared-meter arrangement and investment assumptions are hypothetical. Annual returns extrapolate 30 July days.</div>
<div class="controls"><button class="active" id="short">Round 1 · five minutes</button><button id="deep">Round 2 · algorithm detail</button><label>Demo case <select id="scenario" aria-label="Demo case"></select></label></div>
<p class="tag" id="scope"></p><h2 id="name"></h2><p id="story" class="muted"></p>
<div class="cards" id="metrics"></div><p id="verdict" class="notice"></p>
<div class="section"><h2>What the member pays</h2><div class="split"><div class="card"><span class="tag">Equal ownership</span><strong id="equal"></strong><p>Every member contributes the same amount and receives an equal allocation of savings.</p></div><div class="card"><span class="tag">Consumption based</span><strong id="consumption"></strong><p>Contributions and allocated savings follow gross demand. Different amounts; the same percentage ROI under this allocation.</p></div></div><p class="muted">Both are proposed funding agreements. The community must choose its ownership and benefit rules before purchase.</p></div>
<div id="round1" class="section"><h2>Five-minute pitch run</h2>
<div class="stage"><strong>0:00–0:40 · The problem.</strong> Shared storage is expensive. Members need to know which size fits their community, whether it pays back, and how to split the cost.</div>
<div class="stage"><strong>0:40–1:30 · The starting community.</strong> Open Linden Court. Nine sizes are calculated automatically from recorded data and the catalogue; no member enters tariffs or solar output.</div>
<div class="stage"><strong>1:30–2:40 · The invitation.</strong> In the live app, choose “I'm interested.” Open Solar Commons. Its analysis includes the joining member and recalculates savings, size and contribution.</div>
<div class="stage"><strong>2:40–3:30 · Trust the comparison.</strong> Fixed Tariff Homes has no solar and no price arbitrage: no battery is economically preferable. More capacity does not guarantee a better investment.</div>
<div class="stage"><strong>3:30–4:30 · Choice and database proof.</strong> Accept Solar Commons in the live app. Membership, meter admission and interest change in one Supabase transaction. Viewing an invitation never moves the member.</div>
<div class="stage"><strong>4:30–5:00 · Boundaries and next step.</strong> This is a hypothetical shared-meter replay. Connect actual community meters, contracts and equipment quotes for deployment; validated issued forecasts are the next input.</div>
</div>
<div id="round2" hidden>
<section class="section"><h2>Compare all nine sizes</h2><div class="table-scroll"><table><thead><tr><th>Size</th><th>Installed scenario cost</th><th>Year 1 net saving</th><th>Payback</th><th>10-year cash ROI</th><th>10-year NPV</th></tr></thead><tbody id="options"></tbody></table></div><p class="muted">The highlighted row maximises discounted NPV among feasible options. Negative NPV is compared against doing nothing. Returns stop at the stated service life.</p></section>
<section class="section"><h2>Why 10.24 kWh fits Solar Commons + the member</h2><img class="chart" src="__SIZING__" alt="Battery size versus NPV and annualised savings for Solar Commons plus joining member"><p class="muted">Savings saturate while equipment cost grows. These charts always describe Solar Commons plus the joining member, not the selected alternative case.</p></section>
<section class="section"><h2>One day inside the optimiser</h2><img class="chart" src="__DISPATCH__" alt="15 July prices, community demand, modelled PV, battery charge discharge and stored energy"><p class="muted">Charge during surplus/cheap periods, discharge when needed. Power, grid limits, efficiency and storage reserve constrain every interval. End-of-day charge equals starting charge for a fair comparison. Prices and demand are known in this historical replay.</p></section>
<section class="section"><h2>What is real, and what is a scenario?</h2><div class="table-scroll"><table><tbody>
<tr><th>Consumption</th><td>OPSD/CoSSMic hourly measured household demand. Cumulative counters were differenced; flagged/gapped donor days were excluded. Original timestamps are retained in the fixture archive.</td></tr>
<tr><th>Prices</th><td>OPCOM quarter-hour prices aggregated to hours, then mapped to a documented dynamic import tariff scenario. Export credits are zero.</td></tr>
<tr><th>Solar</th><td>Bucharest ERA5 irradiance proxy: PV capacity × radiation × 0.8. Not measured inverter output; weather reanalysis is not an issued forecast.</td></tr>
<tr><th>Battery</th><td>Deye SE-G5.1 Pro-B LFP modules: 5.12 kWh each; published 4,750.21 RON including VAT, excluding installation. Module banks use a 5 kW inverter cap.</td></tr>
<tr><th>Costs and limits</th><td>Existing compatible inverter, 1,500 RON installation, 100 RON/year maintenance, 90% round-trip efficiency, 2% annual fade, 6% discount rate, ten-year horizon and 20 kW connection limits are scenario assumptions.</td></tr>
<tr><th>Network and membership</th><td>Fictional communities behind a hypothetical compatible shared billing boundary. Switching membership does not physically relocate a home or approve an actual purchase.</td></tr>
</tbody></table></div></section>
<section class="section"><h2>Judges can challenge these cases</h2><ul><li>Why not buy the biggest battery? Follow the sizing/NPV curve.</li><li>Why does a small user pay less under consumption shares? Compare the personal contribution.</li><li>Can the optimiser reject a purchase? Select Fixed Tariff Homes.</li><li>What happens with five complete days? Select Incomplete History: show replay savings but no annual ROI.</li><li>Does viewing an invitation change membership? Verify the account remains in Linden Court until acceptance.</li><li>What survives a restart/sign-in? Membership and preferences are persisted in Supabase; ROI is recalculated.</li></ul></section>
</div>
<footer><strong>Sources and attribution</strong><div id="sources"></div><p>Open Power System Data. 2020. Data Package Household Data, version 2020-04-15. Primary data: CoSSMic / ISC Konstanz. CC-BY-4.0. Derived input archive: research/romania/measured-demand-profiles.csv. Demo preparation: demo/prepare_demo.py. Historical optimal dispatch is an upper-bound reference, not a live forecast or guaranteed return.</p></footer>
</main><script>
const DATA=__DATA__;
const descriptions={
'hackathon-demo-origin':'Linden Court has two members and has declined a shared battery. Its initial analysis uses only its own replay demand and tariffs.',
'hackathon-demo-solar':'Invitation: two solar households plus the joining consumer. Recompute the destination with the incoming member, then compare both funding agreements.',
'hackathon-demo-flat':'Invitation: a small household plus the joining member, no PV and a flat 1.20 RON/kWh tariff. Cycling cannot create price-arbitrage value; equipment and maintenance make purchase uneconomic.',
'hackathon-demo-sparse':'Only five complete replay days. Historical savings are available; annual ROI/payback are deliberately withheld.'};
const nf=new Intl.NumberFormat('en-GB',{maximumFractionDigits:1});
const money=v=>v==null?'Unavailable':nf.format(v)+' RON';
const pb=v=>v==null?'No payback':nf.format(v)+' years';
const sel=document.querySelector('#scenario');
for(const [key,r] of Object.entries(DATA.results)){const opt=document.createElement('option');opt.value=key;opt.textContent=r.community.name;sel.append(opt)}
function show(){const r=DATA.results[sel.value],best=r.best_design_index,d=r.designs[best??0],p=d?.projections?.base;
document.querySelector('#name').textContent=r.community.name;
document.querySelector('#scope').textContent=(r.includes_joining_member?'Invitation including you':'Current community')+' / '+r.member_count+' members / '+r.coverage.replayed_days+' complete replay days';
document.querySelector('#story').textContent=descriptions[sel.value];
const metrics=p?[['Best compared size',nf.format(d.design.capacity_kwh)+' kWh'],['Conditional payback',pb(p.payback_years)],['10-year cash ROI',nf.format(p.roi_pct)+'%'],['10-year NPV',money(p.npv_ron)]]:[['Replay coverage',r.coverage.replayed_days+' days'],['Annual ROI','Withheld'],['Payback','Withheld'],['Sample saving',money(d?.sample_cash_saving_ron)]];
document.querySelector('#metrics').innerHTML=metrics.map(([label,value])=>`<div class="card"><span class="tag">${label}</span><strong>${value}</strong></div>`).join('');
document.querySelector('#verdict').textContent=!p?'Insufficient history: no annual investment prediction.':r.purchase_recommended?'Highest-NPV option under the stated scenario: '+nf.format(d.design.capacity_kwh)+' kWh.':'No compared battery has positive NPV: keeping no battery is financially preferable.';
document.querySelector('#equal').textContent=money(d?.member_allocations?.equal_share?.contribution_ron);
document.querySelector('#consumption').textContent=money(d?.member_allocations?.consumption_share?.contribution_ron);
document.querySelector('#options').innerHTML=r.designs.map((v,i)=>{const f=v.projections?.base;return `<tr class="${i===best?'best':''}"><td>${nf.format(v.design.capacity_kwh)} kWh${i===best?' · highest NPV':''}</td><td>${money(v.design.installed_cost_ron)}</td><td>${money(f?.first_year_net_saving_ron)}</td><td>${f?pb(f.payback_years):'Withheld'}</td><td>${f?nf.format(f.roi_pct)+'%':'Withheld'}</td><td>${money(f?.npv_ron)}</td></tr>`}).join('');}
sel.addEventListener('change',show);show();
document.querySelector('#short').onclick=()=>{document.querySelector('#round1').hidden=false;document.querySelector('#round2').hidden=true;document.querySelector('#short').classList.add('active');document.querySelector('#deep').classList.remove('active')};
document.querySelector('#deep').onclick=()=>{document.querySelector('#round1').hidden=true;document.querySelector('#round2').hidden=false;document.querySelector('#deep').classList.add('active');document.querySelector('#short').classList.remove('active')};
for(const [name,url] of Object.entries(DATA.sources)){const a=document.createElement('a');a.href=url;a.textContent=name;a.target='_blank';a.rel='noopener';document.querySelector('#sources').append(a,document.createTextNode(' · '))}
</script></body></html>'''
page = template.replace('__DATA__', json.dumps(payload).replace('</', '<\\/'))
for name, image in images.items():
    page = page.replace('__' + name.upper() + '__', image)
(PUBLIC / 'index.html').write_text(page, encoding='utf-8')
(ROOT / 'demo/pitch-demo.html').write_text(page, encoding='utf-8')
print('Pitch page ready: http://127.0.0.1:5173/demo/index.html ; offline: demo/pitch-demo.html')
