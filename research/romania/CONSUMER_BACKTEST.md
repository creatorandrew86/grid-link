# Measured consumption: battery backtest and conditional ROI

Computed 5 October 2026. Results and daily cases: [consumer-backtest.json](consumer-backtest.json) and [consumer-backtest.csv](consumer-backtest.csv). Reproduce with [backtest_consumers.py](backtest_consumers.py).

The household reference achieved a **9.82% reduction in the modelled bill after losses and wear with a 5.12 kWh battery**, versus no battery under the same dynamic tariff. It saved more than 0.01 RON on 513 of 548 household-days, or **93.61%**. The remaining 35 cases were effectively idle. The conditional simple payback is **8.09 years**, assuming an existing compatible inverter. A 10.24 kWh battery makes more sense in the tested shared community than in an individual household.

These are simulations combining measured German consumption with Romanian prices and weather. Demand is known in advance in every replay; PV is modelled. The results estimate an opportunity under those inputs. They do not establish live controller performance or an average saving for Romanian households. Annual ROI extrapolates four sampled seasons, rather than testing a full year of prices.

## Real consumption sources

| Source | What it contains | Use here |
|---|---|---|
| [OPSD / CoSSMic, version 2020-04-15](https://data.open-power-system-data.org/household_data/2020-04-15/) | Measured household and business consumption and PV in southern Germany, at resolutions down to one minute | Downloaded the hourly file; selected five residential sites with sufficient feeds to determine gross demand |
| [Low Carbon London, UK Power Networks](https://data.london.gov.uk/dataset/smartmeter-energy-consumption-data-in-london-households-vqm0d) | Half-hourly meter consumption from 5,567 households, November 2011–February 2014, including a dynamic-tariff trial | Larger candidate for the next population test; not included in these results |
| [Romanian household profile, Adrian Fratean / UTCN](https://data.mendeley.com/datasets/ykjcjsnhds/1) | A full-year hourly profile built from appliances and occupancy for a three-person family | Useful Romanian simulation input, but it is constructed rather than measured; not used as real consumer evidence |
| [DEER measurement portal](https://www.distributie-energie.ro/date-de-masurare/) | Access to users' own meter data in DEER concession areas | Possible route to participant data; not a downloaded public household cohort and not the Bucharest distributor |

I did not find a verified public Romanian household meter cohort suitable for this hourly replay. That finding does not imply that such data cannot be obtained from participants or distributors.

The OPSD file has cumulative kWh counters. Hourly consumption must be obtained by differencing, rather than treating counter values as interval energy. The publisher's [processing notebook](https://raw.githubusercontent.com/isc-konstanz/household_data/2020-04-15/processing.ipynb) takes the last reading in each hourly bin. We assign the difference from the preceding row to the current labelled hour; the underlying readings approximate hour-end by the final minute.

For residential sites 3, 4 and 6, gross load is `grid import + PV generation − grid export`. Sites 2 and 5 use grid import directly. Site 1 is excluded because the supplied feeds do not allow the same gross-load reconstruction. The EV and heat-pump demand in site 4 remains part of its fixed measured demand; EV charging is not rescheduled in this experiment.

The parser rejects missing readings, flagged interpolation in either endpoint, nonconsecutive timestamps, counter decreases and materially negative reconstructed demand. Negative gross demand up to 0.003 kWh is clipped as a rounding tolerance. It keeps only complete 24-hour local days, excluding DST days. Rejections are reported in the JSON; counts refer to candidate meter-hours or days, not selected test failures.

From clean 2015–2019 measurements, the script selects unique donor days matching each Romanian target month's season and preferably its weekday. Weekdays match in 97.08% of selected days. Donor days are not reused within a household, and consumption is not scaled. German local clock hours are transferred to Bucharest local clock hours. The original German weather is not contemporaneous with the Romanian replay.

| Residential site | Matched days | Mean gross demand, kWh/day |
|---|---:|---:|
| 2 | 120 | 7.06 |
| 3 | 120 | 15.09 |
| 4 | 120 | 16.02 |
| 5 | 120 | 6.93 |
| 6 | 68 | 24.95 |
| All selected meter-days | 548 | 12.97 |

Four sites cover all 120 Romanian dates. Their sum creates a hypothetical four-home community averaging 45.10 kWh/day. Adding site 6 gives 68 common dates and 74.15 kWh/day. These community sums combine noncontemporaneous donor days and assume one billing meter; they are not observed communities or validated allocations across separately billed connections.

## Prices, weather and battery assumptions

The Romanian data covers January, April, July and 1–28 September 2026: 120 dates and 2,880 hourly intervals. We use collected OPCOM prices and Bucharest ERA5 weather, with the same alignment as [the market report](REPORT.md). Prices are hourly averages of native quarter-hour observations. All strategies are settled against actual replay prices.

The import tariff is the current Bucharest Hidro Dinamic reference analysed in that report: `1.21 × (PZU lei/kWh + 0.5879032)`. Today's charges are held constant over historical prices, so these are reconstructed costs under a tariff scenario, not historical invoices. Export remuneration is an illustrative `PZU − 0.05 RON/kWh`, with uneconomic exports curtailed. An actual prosumer contract could materially change solar results. Battery exports are disabled.

The experiment uses 5.12, 10.24 and 20.48 kWh nominal capacity, 90% round-trip efficiency, a 10% reserve, a 100% maximum state of charge and the same reserve at the start and end of every day. Charge/discharge power is 2.5 kW for one module and 5 kW for two or four modules. Connection limits are 100 kW, effectively nonbinding in this sample. Dispatch applies 0.15 RON per AC kWh discharged as a wear allowance. Daily resets exclude the value of carrying energy across midnight.

Solar cases add an assumed existing 5 kWp system per home or 20 kWp for the shared community. Production is a Bucharest radiation proxy with a 0.8 performance ratio. It does not model roof tilt, module temperature, shading or measured inverter output. Battery thermal restrictions, auxiliary consumption, standby losses, equipment outages and live command delays are not represented.

## Household results

Each row below contains 548 household-days. Bill reduction is `sum(savings after wear) / sum(no-battery bill)`, preserving the same household demand and tariff. This pooled measure avoids letting a tiny daily bill dominate an average of percentages.

| Battery | No-solar bill reduction after wear | Profitable days | Cash saving per tested day, RON | Conditional annual cash saving, RON | Simple payback | 10-year cash ROI |
|---|---:|---:|---:|---:|---:|---:|
| 5.12 kWh | 9.82% | 93.61% | 2.42 | 872 | 8.09 years | +11.67% |
| 10.24 kWh | 11.62% | 93.61% | 2.91 | 1,046 | 11.62 years | −22.09% |
| 20.48 kWh | 12.12% | 93.61% | 3.07 | 1,096 | 20.57 years | −55.96% |

Going from 5.12 to 20.48 kWh increases equipment expenditure substantially but adds only 2.30 percentage points of bill reduction. The larger batteries have little suitable demand left to serve. The 5.12 kWh household scenario's 10-year NPV is −1,056 RON at a 6% discount rate, despite positive undiscounted ROI. It therefore does not meet that assumed return requirement.

Across individual sites, 5.12 kWh no-solar reductions range from 5.22% to 13.45%, with simple payback from 5.12 to 11.66 years. A low bill does not automatically produce an attractive battery investment even when its percentage reduction is high.

With existing 5 kWp PV, the 5.12 kWh battery saves 3.24 RON/day after wear and 3.65 RON/day in energy-bill cash, and is profitable in 98.18% of cases. Its conditional annual cash saving is 1,314 RON, simple payback 5.15 years and 10-year cash ROI +76.22%. Increasing capacity to 10.24/20.48 kWh raises annual cash saving only to 1,461/1,493 RON and lengthens payback to 8.08/14.71 years.

Some solar baseline days already have a net credit. A conventional percentage reduction in a positive bill is therefore not reported for the whole solar cohort. The 5.12 kWh benefit equals 25.16% of baseline **gross grid-import expenditure**, which uses a different denominator from the no-solar bill reduction. The battery ROI is incremental to existing PV; PV purchase cost is excluded.

## Shared community results

The four-home cohort has 120 days per scenario and uses one shared billing meter. Without solar, 113/120 days are profitable (94.17%); with 20 kWp existing PV, 119/120 are profitable (99.17%). All other days are effectively idle, with no materially worse known-price outcomes.

| Battery | No-solar bill reduction | Annual cash saving, no solar | Simple payback, no solar | Annual cash saving, existing 20 kWp PV | Simple payback, PV | 10-year cash ROI, PV |
|---|---:|---:|---:|---:|---:|---:|
| 5.12 kWh | 5.11% | 1,584 RON | 4.21 years | 2,716 RON | 2.39 years | +281.40% |
| 10.24 kWh | 9.09% | 2,851 RON | 4.00 years | 4,728 RON | 2.38 years | +284.05% |
| 20.48 kWh | 11.76% | 3,774 RON | 5.58 years | 5,715 RON | 3.65 years | +150.09% |

The larger shared load uses the battery more often, making 10.24 kWh a stronger candidate than in the household cohort. These annual figures remain conditional extrapolations with known future load and modelled PV. For the PV cases, benefits equal 15.05%, 26.12% and 31.36% of baseline gross import expenditure; they are not conventional net-bill percentages.

The five-home sensitivity is retained in the JSON. For 10.24 kWh it gives 5.23% no-solar bill reduction and 4.20-year simple payback; with 20 kWp PV, payback is 2.59 years. Its coverage is January 31 days, April 6, July 11 and September 20. The uneven calendar and different consumption are reasons to use the four-home cohort for the main comparison.

## Price-estimation strategies and losing days

The forecast experiment uses the same 508 eligible household-days, no PV and a 5.12 kWh battery. Price-estimate schedules are charged at actual historical prices. The corresponding known-price reference on these same days saves 10.40% and is profitable on 95.08% of days.

| Planning-price input | Bill reduction after wear | Profitable days | Worse days | Worst daily loss after wear |
|---|---:|---:|---:|---:|
| Calendar only | 7.37% | 81.69% (415/508) | 18.31% (93/508) | 4.77 RON |
| Calendar + Bucharest weather | 8.06% | 85.63% (435/508) | 14.37% (73/508) | 4.77 RON |
| Calendar + Bucharest + coastal weather | 7.92% | 86.81% (441/508) | 12.99% (66/508) | 5.12 RON |

The regional model has one effectively equal day. It improves on the local-only model by more than 0.01 RON in 75/508 cases (14.76%). A slightly higher profitable-day rate comes with slightly lower aggregate savings and a larger worst daily loss. These results do not support assuming that coastal weather automatically adds a profitable edge.

Training excludes target/future prices and uses earlier available observations, but target weather is actual ERA5 reanalysis. Demand is also known in advance. This is an optimistic weather-information experiment, not a backtest of forecasts issued at the decision time. The regional features are a coastal renewable proxy, not a capacity-weighted national supply/shortage model. Once day-ahead prices are published, use them for the available horizon; price prediction is relevant where published prices are unavailable.

## Published costs and ROI calculation

The base equipment price is the [PowerSense listing](https://powersense.ro/baterie-deye-se-g5-1-pro-b/): from 4,750.21 RON including VAT for a Deye 5.12 kWh module, without installation; configuration and availability must be checked. [Nora Energy lists the same module](https://www.nora-energy.ro/cumpara/baterie-deye-5-12kwh-se-g5-1-pro-b-1027) at 5,566 RON including VAT, with delivery extra. These are published prices, not an accepted installation quote.

| Battery | Modules | Equipment at base price | Assumed installation | Base investment with existing compatible inverter |
|---|---:|---:|---:|---:|
| 5.12 kWh | 1 | 4,750.21 RON | 1,500 RON | 6,250.21 RON |
| 10.24 kWh | 2 | 9,500.42 RON | 1,500 RON | 11,000.42 RON |
| 20.48 kWh | 4 | 19,000.84 RON | 1,500 RON | 20,500.84 RON |

Installation is an assumption that must cover the required balance-of-system work, not a sourced installer quote. The report also assumes 100 RON/year operating cost. Annual cash saving is 365 times the mean daily cash saving, first averaging within each home's sampled month, then equally across its four seasons and across homes. This prevents the home with fewer clean days from being assigned a smaller investment weight. Sample-period percentages use all selected cases, so their weighting differs from the annual financial projection.

Simple payback is `initial investment / (annual cash saving − annual operating cost)`, with no discounting or degradation. First-year net cash return, also stored in JSON, is 12.36%, 8.60% and 4.86% for the three no-solar household sizes.

The 10-year projection applies 2% annual savings fade, 100 RON/year operating cost, no replacement and no terminal value. Cash ROI is `(sum of ten annual net cash flows − initial investment) / initial investment`. NPV discounts each year's net cash flow at 6%. Financing, subsidy, tariff escalation and tax changes are excluded. A year-by-year degradation assumption is not a forecast of this particular product's service life.

Dispatch wear is a noncash decision penalty. Bill-reduction figures include it, while cash ROI uses actual energy-bill savings before that penalty and pays for the battery through initial investment. Subtracting both the full wear allowance and initial battery capital from the same financial cash flow would double count the capital cost. This treatment still requires real degradation/replacement modelling before an investment decision.

The [Deye manufacturer datasheet](https://deye.com/wp-content/uploads/2026/01/deye-se-g5.1-pro-b-series_brochure-20260115auv1.0.pdf) states at least 6,000 cycles under specified temperature, rate and depth-of-discharge test conditions, and a 10-year warranty subject to conditions with a 16 MWh energy-throughput reference at 70% end-of-life capacity. It does not justify promising ten years of arbitrary cycling. At extrapolated first-year use, the four-home 5.12 kWh scenarios approach that reference in about 8.8 years, versus about 9.2–9.9 years for 10.24 kWh. These approximate conversions account for modelled discharge efficiency; confirm the warranty's throughput definition and conditions. The threshold is not an assumed failure date.

Useful household 5.12 kWh sensitivities:

- A 6,000 RON assumed inverter retrofit extends no-solar simple payback from 8.09 to 15.86 years; with existing PV it extends payback from 5.15 to 10.09 years.
- Using the 5,566 RON module price instead gives 9.15-year no-solar simple payback before any extra delivery cost.
- If annual gross savings are 25% lower or higher, no-solar payback is about 11.28 or 6.31 years, respectively.
- Doubling dispatch wear to 0.30 RON/kWh reduces no-solar modelled bill reduction from 9.82% to 7.61%, with 89.05% profitable days and 8.57-year simple cash payback. It changes the schedule as well as the reported economic saving.

## Checks and reproduction

The batch completed **6,488 scenario-days**: 4,964 known-price cases, including wear and community sensitivities, plus 1,524 price-estimate cases. **100% passed the batch's energy-balance, state-of-charge, power-limit, operating-mode and equal-final-charge assertions.** This is a technical pass rate, distinct from the profitable-day rates above. A known-price schedule can always remain idle in these scenarios, so avoiding losses in that reference is expected from the objective; it is not evidence of forecast accuracy.

All **11 backend automated checks passed**. Three new regression checks cover cumulative-meter alignment and PV reconstruction, flagged-feed rejection and cash ROI accounting/uneven sample weighting. The existing checks cover accounting, API validation and the battery optimiser's hand-calculated examples and physical constraints.

From the repository root, with the prepared environment:

```powershell
.\.tools\venv\Scripts\python.exe -m unittest discover -s backend -v
.\.tools\venv\Scripts\python.exe research/romania/backtest_consumers.py
```

For a new environment, install `backend/requirements.lock.txt` first. The first backtest run downloads public OPSD files into ignored `research/romania/raw/`; later runs use the cache. It reads the existing Romanian price/weather dataset, uses the production battery solver and does not change the app's database or settings. [measured-demand-profiles.csv](measured-demand-profiles.csv) records every transferred hour with its source date/timestamp. JSON records the raw-file SHA-256 and all daily results.

OPSD attribution: Open Power System Data. 2020. Data Package Household Data. Version 2020-04-15. Primary data: CoSSMic / ISC Konstanz. Source data and these derived demand profiles are attributed under CC BY 4.0. Price and weather provenance remains in [REPORT.md](REPORT.md) and [metadata.json](metadata.json).

For GridLink, the next useful trial is advisory scheduling with actual participant demand/PV and published prices. Compare 5.12 and 10.24 kWh for a shared installation, collect issued weather forecasts and load forecasts, and settle every proposed schedule against subsequent meter readings. Preserve idle operation when margins are weak. Extend the Romanian price sample to a full consecutive year and rerun installed-cost, export-contract, battery-temperature and replacement sensitivities before treating any projected ROI as an investment result.
