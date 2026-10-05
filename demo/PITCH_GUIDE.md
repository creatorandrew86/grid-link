# Hackathon demo: ready to rehearse

App: http://127.0.0.1:5173/#login

Main account: **pitch@gridlink.demo** / **GridLinkPitch26!**

Pitch visuals: http://127.0.0.1:5173/demo/index.html

Offline backup: open [pitch-demo.html](pitch-demo.html). It contains its results and charts, so it works without a backend or internet connection. Membership acceptance itself is demonstrated in the live app.

The app's real Supabase database contains four isolated `hackathon-demo-*` communities, six fictitious accounts, six approved demonstration PODs, preferences and 2,280 hourly replay records. No actual community measurements were created or overwritten. The dedicated demo archive is stored as `mode=demo_battery` in `clearing_events`; `community_meter_intervals` is untouched. Demo metadata uses the existing community description column, so no new migration is needed. Normal measured analysis excludes demo records.

## Five-minute first-round run

| Time | Show | Say |
|---|---|---|
| 0:00–0:40 | Landing page | Shared batteries need a community decision: right size, realistic economics, and an agreed contribution. |
| 0:40–1:30 | Sign in → Account → Linden Court | The member sees their current community's automatically calculated options. Nine sourced modular LFP sizes; no manual tariff, load or solar entries. |
| 1:30–2:40 | Click **I'm interested** → Solar Commons invitation | Linden Court has declined. The invitation recalculates the destination including this member. Best compared size is 10.24 kWh; conditional payback about 2.7 years. |
| 2:40–3:30 | Fixed Tariff Homes invitation | The algorithm also says no: without solar or tariff variation, storage has no arbitrage value and no positive NPV. |
| 3:30–4:30 | Review Solar Commons → Accept and switch | Joining is voluntary. The database changes membership, POD admission and preference atomically, then records the accepted transfer. Viewing an invitation alone changes nothing. |
| 4:30–5:00 | Show the new account community | This is a labelled replay. Next comes connecting actual community measurements, contracts and validated forecast feeds. Membership persists after signing out/in. |

## Cases and computed results

These are ten-year scenario results annualised from **30 July 2026 replay days**, not full-year measured returns. Installation, efficiency, maintenance and finance assumptions are disclosed on screen. Current community interest is a scripted demonstration decision, not a real survey.

| Case | What it demonstrates | Best compared size | Conditional payback | Ten-year NPV |
|---|---|---:|---:|---:|
| Linden Court | Current community; two measured donor consumption profiles; no PV | 5.12 kWh | 6.2 years | +949.57 RON |
| Solar Commons + joining member | Recomputed invitation; three members; modelled 20 kWp existing PV | 10.24 kWh | 2.7 years | +17,147.22 RON |
| Fixed Tariff Homes + joining member | Flat 1.20 RON/kWh import, no PV, zero export credit: purchase rejected | Best battery still loses money | No payback | −6,986.22 RON |
| Incomplete History | Five complete days: historical replay allowed, annual ROI withheld | No annual recommendation | Withheld | Withheld |

For Solar Commons, the selected battery's installed **scenario** cost is 11,000.42 RON. Equal contribution is **3,666.81 RON** for the joining member; demand-proportional contribution is **2,079.24 RON**. Those two rules allocate savings by the same shares as cost; percentage ROI/payback therefore remain equal. Gross demand is a practical allocation rule, not a measurement of each household's causal battery benefit.

Other demo logins use the same password. Use **sparse-one@gridlink.demo** to show incomplete history directly in the app. **solar-one@gridlink.demo** is a prosumer account. Their data is fictitious-account data built from published inputs, never actual customer data.

## Second-round representation

Select **Round 2 · algorithm detail** on the pitch page. Show:

1. All nine capacities: 5.12, 10.24, 15.36, 20.48, 30.72, 40.96, 61.44, 81.92 and 102.4 kWh. They are modular banks of the same real LFP product, not invented prices for NMC or lead-acid equipment.
2. [Sizing curves](../public/demo/sizing.png): savings saturate; growing equipment cost reduces NPV. Highest NPV is the selection criterion.
3. [Hourly dispatch](../public/demo/dispatch.png): demand, PV, tariffs, charge/discharge, stored energy and grid imports on 15 July. The battery fills before evening imports, while preserving limits and the same start/end charge.
4. Equal versus demand-proportional funding: personal amounts change with the roster and usage.
5. Data-quality refusal: insufficient history gives no annual prediction; an uneconomic battery is not recommended.
6. Supabase persistence: show the demo participant's `community_id`, approved POD's community, saved interest and accepted `community_transfer_requests` record after a switch. Demo IDs are listed below.

The known-price optimiser is a constrained historical upper-bound reference. It balances energy each hour, enforces charge/discharge/grid limits, accounts for round-trip losses, avoids simultaneous opposing flows and closes each day at its starting reserve. Investment cash flow counts capex once, includes maintenance and fade, discounts to NPV and compares against no purchase.

## Data provenance and assumptions

- [OPSD/CoSSMic household dataset, version 2020-04-15](https://data.open-power-system-data.org/household_data/2020-04-15/): measured southern German consumption. The existing parser differences cumulative counters and excludes flagged/gapped donor days. Selected original donor timestamps remain in every replay fixture. German clock-hour profiles are transferred to Romanian July dates; the assembled communities were never physically measured together.
- [OPCOM published day-ahead prices](https://www.opcom.ro/rapoarte-pzu-raportPIP-export-csv): existing collected quarter-hour Romanian observations aggregated to hours. Demo dynamic import is `1.21 × (PZU + 0.5879032)`; current charges held over historical prices constitute a reconstructed tariff scenario, not historical invoices. Fixed Tariff Homes uses an explicit alternative flat scenario.
- [Open-Meteo historical weather / ERA5](https://open-meteo.com/en/docs/historical-weather-api): Bucharest irradiance drives `PV kWp × GHI / 1000 × 0.8`. This is modelled PV, not real community inverter output or an issued weather forecast. Export credit is zero, so surplus has no invented sale value.
- [PowerSense published Deye SE-G5.1 Pro-B listing](https://powersense.ro/baterie-deye-se-g5-1-pro-b/), checked 5 October 2026: 4,750.21 RON/module including VAT, excluding installation. [Manufacturer datasheet](https://deye.com/wp-content/uploads/2026/01/deye-se-g5.1-pro-b-series_brochure-20260115auv1.0.pdf): LFP, 5.12 kWh/module, recommended 50 A at 51.2 V, scalable modular bank, ten-year warranty with conditions. Warranty is used as the demo horizon, not a guarantee of lifetime.
- Scenario assumptions: compatible existing 5 kW inverter; 1,500 RON installation; 20 kW import/export limits; 90% system round-trip efficiency; 90% usable fraction; 2% annual fade; 100 RON/year maintenance; 6% discount rate; 0.15 RON/kWh dispatch wear allowance. Published module prices are not an accepted installed quote. A real project needs verified equipment/settlement compatibility.

Attribution: Open Power System Data. 2020. Data Package Household Data. Version 2020-04-15. Primary data: CoSSMic / ISC Konstanz. CC-BY-4.0. The source data and research methodology are already under `research/romania/`; the demo does not require another large download.

## Reset and checks

Before another rehearsal, run from the repository root:

```powershell
.\demo\reset_demo.cmd
```

This resets only our six demo accounts' memberships/PODs and their interest preferences. It does not delete records or accepted-transfer history. It rebuilds the static results/charts. The default pitch account returns to Linden Court and starts not interested, ready to click **I'm interested** during the presentation.

To reproduce the full live verification (it deliberately switches the pitch account to Solar Commons, so reset again afterwards):

```powershell
.\.tools\venv\Scripts\python.exe demo/verify_live_demo.py
.\demo\reset_demo.cmd
```

The successful live check is recorded in [live-verification.json](live-verification.json). It verifies login, source labels, nine sizes, saved interest, eligible invitations, both economic outcomes, no movement on preview, atomic switch, post-switch funding, unchanged invitation economics after acceptance and persistence across sign-in.

Demo community UUIDs:

| Community | UUID |
|---|---|
| Linden Court | `86383f9a-517c-594d-831f-1a5d4727d053` |
| Solar Commons | `7cd5e77e-45f1-57fa-8205-b8023a7e66e1` |
| Fixed Tariff Homes | `129f4162-5c89-5b13-a6e5-d698e803dfce` |
| Incomplete History | `f9dad872-ce81-5690-ae96-52bfca8739e3` |

## Likely judge questions

**Are these Romanian customer meters?** No. Public measured German donor demand is replayed with Romanian prices and weather. The app labels the hypothetical communities explicitly.

**Is 2.7 years guaranteed?** No. It is conditional annualisation of 30 summer days with known future demand/prices and declared costs. Real meters, annual seasonal coverage, equipment quotes and issued forecasts must be validated before purchase.

**Does joining move the meter?** No. It changes account membership in a hypothetical compatible shared-billing demo network. Real deployment requires an eligible physical/settlement arrangement.

**Why no weather forecasting accuracy claim?** ERA5 is historical reanalysis. The deeper research backtests already show losing forecast-price days; this pitch does not pretend they establish issued-forecast performance.

**Do you collect money or control a real battery?** No. The demonstrated actions are analysis, preference saving and voluntary membership switching.
