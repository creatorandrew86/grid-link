# Battery optimiser and regional weather experiment

Implemented 4 October 2026. Open the application at `http://127.0.0.1:5173/#battery`.

The follow-up [measured-consumption backtest](CONSUMER_BACKTEST.md) evaluates the same solver on five public household meter profiles, with daily success/loss rates and conditional battery ROI. It also compares the price-estimation variants on a common sample.

## What runs now

The simulator uses the collected hourly Romanian prices and ERA5 weather. A scenario specifies demand, PV capacity, battery capacity/power, efficiency, reserve, wear and import/export contract assumptions. It represents one shared billing meter. It does not combine separately billed connections or issue equipment commands.

There are six comparisons:

- No battery, with immediate PV self-consumption/export and curtailment when exporting is uneconomic.
- Night-only: the best feasible schedule restricted to charging at 00:00–06:00 and discharging at 18:00–23:00. It can use partial cycles or remain idle.
- Optimised: a whole-day schedule using the actual published prices and scenario demand/PV. Its historical weather input makes it a reference for that assumed system, rather than a forecast-performance claim.
- Calendar estimate: scheduling against estimated prices from time/calendar features.
- Local weather: the same model with Bucharest radiation and temperature features.
- Local + coastal weather: additionally use Constanța/Tulcea radiation and an illustrative wind-generation proxy.

All estimated-price schedules are settled at the actual historical prices. They can lose money compared with leaving the battery idle. The app shows those losses.

The mixed-integer optimisation minimises import purchases minus export revenue plus wear. It enforces energy balance, charge/discharge power, grid power limits, minimum/maximum stored energy and exclusive charge/discharge/import/export operating modes. Every replay ends at its starting state of charge. Dataset gaps never carry stored energy across months. [SciPy mixed-integer solver documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.milp.html).

The initial model uses hourly prices, matching the paired weather dataset. Native quarter-hour prices remain in the repository. Confirm the contract's settlement granularity before claiming a quarter-hour benefit.

## Your proposed export opportunity

The proposed situation is plausible: our network has surplus PV while renewable generation elsewhere is weak, and the available export price is high. We can sell immediately, retain energy for an even better later price, or use it to avoid our own purchases. The optimiser compares those opportunities after losses and wear.

The reverse situation also matters: cloudy conditions here while wind or solar elsewhere is strong may coincide with inexpensive grid energy. We could charge from the grid for our later deficit, provided the final billed price difference covers losses and wear. Both situations require price or price-forecast evidence; a weather mismatch alone does not establish either opportunity.

An approximate condition for retaining one unit of surplus PV for later export is:

`later net export price > current net export price / round-trip efficiency + wear per delivered kWh`

Avoiding a later import must also be compared with selling. Retail import charges can make self-consumption more valuable than wholesale-linked exports. A high OPCOM price benefits us only to the extent our actual export contract passes it through. The example export contract in the simulator is adjustable; it is not a claim about a prosumer's legal settlement entitlement. Selling grid-charged battery energy also needs a compatible connection and contract.

Weather needs to be attached to the kind and location of generation. Wind/solar output reacts within hours. Hydro depends on catchment conditions, inflow, reservoir levels and operator decisions over longer periods; tomorrow's city rainfall is not a hydro-production forecast. Nuclear and thermal output require availability/outage information and, where relevant, cooling-water conditions.

Transelectrica identifies renewable integration in Dobrogea and Banat and reports substantial hydro, nuclear and thermal capacity as well as wind/solar. Two coastal weather points cannot represent national supply. [Transelectrica preliminary 2025 report](https://www.transelectrica.ro/documents/10179/21404179/Raport_ASF_T4_Preliminar_2025_RO.pdf/d3ed2816-6b29-4429-bb5a-b8a72e18bad2).

ACER also identifies evening flexibility shortages and constrained cross-border imports as factors in Southeast European price spikes. Even an accurate Romanian renewable forecast leaves demand, interconnectors and neighbouring markets to account for. [ACER regional assessment](https://www.acer.europa.eu/monitoring/MMR/crosszonal-electricity-trade-capacities-2026).

Once next-day prices are published, those prices should drive the relevant horizon. Weather continues to inform our PV/demand expectations. Weather-based price estimation is useful to investigate before publication, beyond the published horizon and for later market decisions whose prices remain unknown. The current optimiser uses historical day-ahead prices; it does not model intraday trading. [OPCOM operating schedule](https://www.opcom.ro/tranzactii-produse/ro/1).

## What the current data shows

The reproducible experiment uses ridge regression with hour-of-day, weekend and annual calendar features. All variants use the same training window: up to 28 earlier available data days, excluding the entire preceding day so training weather is already historical before a previous-day planning decision. At least seven training days are required.

Local features are radiation plus illustrative heating/cooling thresholds of 18°C and 22°C. Coastal features are mean Constanța/Tulcea radiation and the average of a generic turbine curve: zero below 3 m/s or at/above 25 m/s, cubic growth to rated output at 12 m/s. These are assumptions, not measurements of Romania's renewable fleet. Predictions are bounded to −2 to 5 RON/kWh to limit extrapolation from this small dataset; those bounds are not market price limits.

The held-out target day's weather is **ERA5 reanalysis, not an archived forecast issued beforehand**. This tests weather information under optimistic availability and does not validate a live trading edge. Training windows can span large missing periods: early September lacks August training data. Four selected months are insufficient for annual return estimates.

For the default 50 kWh/day demand, 20 kWp horizontal-plane PV proxy, 20 kWh battery, 5 kW power, 90% round-trip efficiency and 0.15 RON/discharged-kWh wear, the incremental average benefit of adding coastal features to the local-weather model was:

| Sample | Evaluated days | Additional benefit, battery exports disabled (RON/day) | Additional benefit, battery exports enabled (RON/day) | Days helped, exports enabled |
|---|---:|---:|---:|---:|
| January | 23 | 0.004 | 0.004 | 6 |
| April | 30 | 0.336 | 0.317 | 15 |
| July | 31 | 0.116 | 0.445 | 6 |
| September 1–28 | 28 | 0.895 | 0.895 | 7 |

These are conditional simulation results after wear, before equipment cost. They compare model variants, not the battery against no storage. Small average gains and occasional larger gains do not establish forecast reliability. The full weather model also failed to improve calendar-only average price error in January and July. Lower price error does not guarantee better scheduling: errors around the chosen charging/export hours matter more than errors elsewhere.

The “Surplus for export” preset uses 1 September, 15 kWh demand, 30 kWp PV and the default battery, with battery exports enabled. The perfect-information replay improves the modelled net bill from −49.36 to −66.53 RON, a 17.17 RON benefit after wear. Those values rely on the assumed PV/demand and export contract; they are not observed community earnings.

Exact daily results and assumptions are in [weather-experiment.json](weather-experiment.json). Reproduce them from the repository root:

```powershell
.\.tools\venv\Scripts\python.exe research/romania/check_weather_strategy.py
```

## Current forecasts

The outlook fetches the next 48 full forecast hours from Open-Meteo's ECMWF IFS model for Bucharest, Constanța, Tulcea, Arad, Craiova and Giurgiu. It displays regional irradiation/wind and experimental wholesale price estimates. The trained price model uses the three locations represented in our historical dataset; the other three currently provide regional context only. No capacity-weighted national generation estimate is claimed.

Wind is requested in m/s at 100 metres. Radiation at timestamp t+1 describes the preceding hour and is aligned with the interval starting at t. Temperature/wind are taken at the interval start. The retrieval timestamp is recorded; this endpoint does not supply an exact model issuance timestamp. Price estimates are distinct from published OPCOM prices. If the provider is unavailable, the historical simulator still works. [Open-Meteo ECMWF documentation](https://open-meteo.com/en/docs/ecmwf-api).

The historical mismatch signal is illustrative: local scenario surplus plus coastal wind proxy below 20% and coastal radiation below 70% of local radiation. It identifies a candidate situation for investigation, not a measured national shortage or calibrated shortage probability. Strong coastal wind above 50% or radiation above 500 W/m² produces a broad-renewable-availability label. Labels do not override the optimiser's prices.

## What is needed before using this to trade

1. Confirm our import/export contract, settlement interval, connection limits and whether stored/grid-charged energy may be exported.
2. Add measured demand/PV and battery telemetry. Calibrate the PV model, which currently scales horizontal GHI by capacity and performance ratio, without tilt, module temperature or detailed inverter modelling.
3. Collect issued forecasts across generation regions, with model run and availability timestamps. Align them with installed/available wind and solar capacity and measured generation, including western/southern PV coverage.
4. Add national demand, outages, hydro conditions, interconnector availability and neighbouring prices. Evaluate their incremental value instead of attributing every price move to weather.
5. Run chronological tests using forecasts available at each decision. Compare local-only versus regional models on realised bills, downside losses and error, then run advisory schedules before equipment control. [Open-Meteo archived individual forecast runs](https://open-meteo.com/en/docs/single-runs-api).

The scheduling function accepts interval demand, PV and planning prices separately. Future EV schedules can add charging demand and deadlines to the energy constraints; a stationary battery is not required simply to move EV charging into cheaper hours.
