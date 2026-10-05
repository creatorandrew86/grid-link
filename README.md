# GridLink

GridLink is a community energy market prototype built for the Vianu Hackathon project. It models how households and businesses can share surplus solar electricity and divide the financial benefit between people who produce energy and people who consume it.

Members join as consumers or prosumers. For each 15-minute interval, GridLink estimates production and demand, allocates available solar surplus across the community, calculates the buying and selling prices, and compares each member's resulting bill with a grid-only benchmark. The pricing coefficient and transport cost split can be adjusted from the dashboard.

The application has a React/Vite/Tailwind frontend, a Python FastAPI backend, and a persistent SQLite database for local use. Supabase storage integration, database migrations, and functions for scheduled clearing are included for a later connection to a hosted project. The frontend follows `.codex/DESIGN.md`.

A separate battery simulator now replays real Romanian hourly prices and weather, compares charging/export schedules and tests experimental regional-weather price estimates. Its settings and RON calculations are independent of the original community interval demonstration.

## Purpose and scope

The project explores a simple question: how much value could a community retain if a producer's surplus were sold to another member at a price between the grid export and import tariffs?

In the model, a prosumer first uses their own solar production. Any surplus can be allocated to other members who still need electricity. Buyers pay the community buying rate for that allocation, while sellers receive the community selling rate. Demand that cannot be met locally is purchased from the grid, and surplus that cannot be sold locally is exported to the grid.

GridLink makes this allocation and its financial effect visible. A user can inspect the community's energy balance, compare individual bills, and experiment with the terms of local trading. The first version focuses on one interval at a time so that the pricing and accounting can be checked before adding forecasts or scheduling.

The current application is a simulation using entered demand, installed solar capacity, and a configurable solar output factor. It does not control electricity routing, connect to smart meters, execute energy transactions, or collect payments. The transport fee is a configurable cost in the model; its default value is a sample input, not a verified network charge.

## Run locally

On this workspace, dependencies are installed. From the repository root:

The backend requires Supabase credentials. On a fresh checkout, copy `.env.example` to `.env.local` in the repository root and fill in `SUPABASE_URL` and `SUPABASE_SECRET_KEY` (or the legacy `SUPABASE_SERVICE_ROLE_KEY`). Use plain values without quotation marks. The backend loads this file; Git ignores it.

```powershell
Copy-Item .env.example .env.local # First setup only; then fill in your credentials.
.\dev.cmd
```

Open http://127.0.0.1:5173. API documentation is at http://127.0.0.1:8000/docs. The launcher starts hidden local processes and prints their PIDs. Stop them with `Stop-Process -Id <PID>`. Logs are in `.tools/`. The CMD launcher permits its PowerShell script for that invocation only; it does not change the system execution policy.

For a fresh checkout with the locked scientific dependencies, use Python 3.12+ and Node.js 22.12+:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.lock.txt
npm.cmd ci
.\dev.cmd
```

Or run two terminals manually:

```powershell
# Backend, from the repository root
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
# Frontend, from the repository root
npm.cmd run dev
```

This machine's MSYS Python cannot load the required native wheels, so the prepared launcher uses an isolated CPython environment in `.tools/venv/`.

Frontend npm commands run from the repository root, where `package.json`, `package-lock.json`, and `vite.config.js` live. In PowerShell, use `npm.cmd` if script execution blocks `npm.ps1`. Vite serves `frontend/index.html` and `frontend/src/`, reads static assets from the root `public/` folder, and writes production output to the root `dist/` folder.

## Implemented functionality

- Join as a consumer or prosumer. Participants and market settings survive a backend restart.
- View grid and community buying/selling rates, energy flow, member bills, and savings for a 15-minute interval.
- Tune grid tariffs, the price weight, transport fee, buyer/seller transport split, and estimated solar output.
- Preview pricing without saving it, save it for the whole community, or discard changes.
- Sign in to inspect your own bill comparison. Individual community records are not public.

The first local database includes six clearly labelled example members. Set `GRIDLINK_SEED_DEMO=0` before creating a new database to start empty. The database lives at `backend/data/gridlink.db`; override its path with `GRIDLINK_DB_PATH`.

### Participant flow

A new member opens the join form, enters a home or business name, chooses a role, and provides their estimated average electricity demand. A prosumer also enters their installed solar capacity. The backend validates the submission, assigns an ID, and stores the participant.

After joining, the backend issues a session and the account page shows the new participant's own bill. Sign-in also issues a session. Session tokens are random, expire after 24 hours, and are stored in browser local storage. Sessions currently live in a single backend process: restarting it requires signing in again, and multiple workers require shared session storage. Old `gridlink-<id>` tokens are rejected.

The participant roles are:

| Role | Input and behavior |
| --- | --- |
| Consumer | Enters demand and has zero solar capacity. Buys available community solar, then uses the grid for any remaining demand. |
| Prosumer | Enters demand and a positive solar capacity. Uses their own production first, sells surplus when available, and can buy energy when production is below demand. |

A prosumer's role does not guarantee that they sell in every interval. Their position depends on their estimated production relative to their demand.

### Dashboard

The overview displays grid import, grid export, local buying, and local selling rates. Local buying includes the buyer's transport share; local selling is the seller's net rate after their transport share is deducted.

The energy flow section shows estimated solar production, self-consumption, locally traded energy, community demand, grid imports, grid exports, and the transport amount collected. The community bill comparison shows the combined net cost with and without local sharing.

The community ledger is removed for everyone. The overview shows aggregate community figures; the account page shows only the signed-in member's role, energy, bills, and benefit. All bill figures refer to the displayed interval; they are not daily or monthly forecasts.

The market settings section allows a user to change the pricing assumptions. Preview recalculates the displayed results without changing the stored configuration. Save persists the configuration for the whole community, and Discard returns to the saved values. Refreshing the market also loads the saved configuration.

### Interface design

The visual reference uses black surfaces, caution yellow (`#fff313`), industrial white (`#eeeeee`), restrained gray borders, and light headline weights. The interface alternates these surfaces, uses small corner radii, and avoids gradients and shadows. A technical solar-panel illustration supports the energy context.

The layout adapts to desktop and mobile screens. Controls have labels, the signup form uses a native dialog, status and error messages are announced through accessible regions, and the member table can scroll horizontally on small screens. Interface text describes the current simulation and its inputs directly.

## Participant data and units

Each participant has the following stored fields:

| Field | Meaning | Validation |
| --- | --- | --- |
| `id` | Server-generated participant identifier | Assigned during signup |
| `name` | Home or business name | Trimmed; 2 to 80 characters; duplicate names are rejected |
| `type` | Participant role | `consumer` or `prosumer` |
| `load_kw` | Estimated average demand during the interval | From 0 to 1,000 kW |
| `solar_kwp` | Installed solar capacity | From 0 to 1,000 kWp; zero for consumers and positive for prosumers |

Power and energy use different units. `load_kw` is power, while the amount consumed over an interval is energy in kWh. `solar_kwp` is the installed peak capacity used by the production estimate. Prices are in EUR per kWh, and bills are in EUR per interval.

With the current 15-minute interval, `interval_hours` is `0.25`. A constant demand of 2 kW therefore corresponds to 0.5 kWh consumed during the interval.

The current inputs remain constant until the shared market assumptions change or a new participant is added. The solar output factor applies uniformly to every prosumer. Time-dependent demand profiles, per-site production factors, and weather forecasts are future work.

## Pricing and allocation

All sample prices are in EUR per kWh. They are simulation inputs, not current utility tariffs.

```text
clearing_price = grid_sell + price_weight × (grid_buy − grid_sell)
buyer_rate    = clearing_price + transport_fee × buyer_transport_share
seller_rate   = clearing_price − transport_fee × (1 − buyer_transport_share)
```

`price_weight` replaces the fixed `0.60`. Its default is 0.60 and its range is 0–1. Transport defaults to €0.015/kWh, split 50/50. With the sample €0.30 import and €0.08 export tariffs, the clearing price is €0.212, the buyer pays €0.2195, and the seller receives €0.2045.

### Configurable market parameters

| Parameter | Default | Meaning |
| --- | --- | --- |
| `grid_buy` | €0.30/kWh | Price paid for electricity imported from the grid |
| `grid_sell` | €0.08/kWh | Price received for electricity exported to the grid |
| `price_weight` | 0.60 | Position of the clearing price within the gap between grid export and import prices |
| `transport_fee` | €0.015/kWh | Total modeled transport cost for each locally traded kWh |
| `buyer_transport_share` | 0.50 | Fraction of the transport fee paid by the buyer; the seller pays the remainder |
| `solar_yield_factor` | 0.75 | Estimated production as a fraction of installed solar capacity |

The price weight and transport split answer different questions. The price weight sets the energy price before transport. Raising it moves the price toward the grid import tariff, increasing the seller's gross revenue and reducing the buyer's energy-price saving. The transport split determines who bears the fee after that price is calculated.

At a buyer transport share of `0`, the seller pays the entire fee. At `1`, the buyer pays the entire fee. At `0.50`, each side pays half. The fee is charged once per traded kWh: the buyer's payment minus the seller's receipt equals the total fee.

Tariffs and transport fees must be finite values between 0 and 10 EUR/kWh. The price weight, buyer transport share, and solar output factor must be between 0 and 1. The grid export price cannot exceed the grid import price.

### Worked pricing example

Using the defaults, the tariff gap is `0.30 - 0.08 = 0.22`. The clearing price is `0.08 + 0.60 × 0.22 = 0.212` EUR/kWh. A 50/50 transport split assigns `0.0075` EUR/kWh to each side.

For one kWh that would otherwise be bought from and sold to the grid:

| Item | Grid benchmark | Local sharing |
| --- | --- | --- |
| Buyer payment | €0.3000 | €0.2195 |
| Seller receipt | €0.0800 | €0.2045 |
| Buyer saving | No local-sharing benefit | €0.0805 |
| Seller additional earnings | No local-sharing benefit | €0.1245 |
| Combined member benefit | No local-sharing benefit | €0.2050 |
| Modeled transport cost collected | No local-trade fee | €0.0150 |

These figures apply only to the quantity actually traded locally. Electricity supplied by or exported to the grid continues to use the corresponding grid tariff.

For a fixed clearing price and a competitive trade, changing the transport split redistributes the benefit between buyer and seller. It does not change the total fee or the combined benefit per traded kWh. Changing the split can, however, make the resulting rates uncompetitive for one side and pause trading.

### Energy allocation

For each interval, generation is `solar_kwp × solar_yield_factor × interval_hours`. Each prosumer consumes their own solar first. The engine matches the lesser of total surplus and remaining demand, allocated proportionally among sellers and buyers. Grid imports cover unmet demand; the grid buys unsold surplus. The benchmark uses the same solar/self-consumption with all surplus and deficits settled at grid tariffs. Savings include transport costs. A negative bill means net earnings.

The engine follows these steps:

1. Convert each member's demand and estimated production into interval energy.
2. Allocate the lesser of their production and demand to self-consumption.
3. Calculate each member's remaining deficit or surplus.
4. Check whether the local buying and selling rates are competitive with the grid.
5. Match the lesser of total community surplus and total remaining demand when trading is enabled.
6. Divide matched energy among buyers in proportion to their deficits and among sellers in proportion to their surpluses.
7. Calculate residual grid imports and exports, then produce member and community bill comparisons.

This is a pooled allocation. It does not choose named buyer-seller pairs, prioritize particular members, or calculate routes through a physical network. A member with twice another buyer's deficit receives twice as much of the available local allocation, subject to the total matched quantity.

When production is zero, members obtain their demand from the grid. When supply exceeds demand, the unmatched surplus is exported. When demand exceeds supply, the grid supplies the remaining deficit. An empty community produces zero energy and bill totals.

### Bills and benefit

The benchmark assumes that members keep the same solar production and self-consumption, but settle all remaining demand and surplus through the grid. This makes the comparison measure the effect of sharing rather than the effect of installing solar.

```text
benchmark_bill = deficit_kwh × grid_buy − surplus_kwh × grid_sell

gridlink_bill = grid_import_kwh × grid_buy
              + local_bought_kwh × buyer_rate
              − grid_export_kwh × grid_sell
              − local_sold_kwh × seller_rate

benefit = benchmark_bill − gridlink_bill
```

Positive bills are net costs; negative bills are net earnings. A seller can therefore benefit when their GridLink bill becomes more negative. Community totals sum the member results, including both payments and export earnings. A very small community net bill does not mean that every member has a small individual bill.

### When local trading pauses

If the local buying rate exceeds grid import or the selling rate falls below grid export, local trading pauses. Money calculations use Python Decimal; API outputs retain nine decimal places and the UI rounds for display. This is a simulation, without invoices or payments.

The eligibility conditions are `buyer_rate <= grid_buy` and `seller_rate >= grid_sell`. Both must hold. Equality is allowed, so a trade can have zero benefit for one side. When either condition fails, the model allocates no local trades and uses the grid benchmark for the interval.

For an eligible traded kWh, the buyer's saving is `grid_buy - buyer_rate` and the seller's additional earnings are `seller_rate - grid_sell`. Their combined benefit is `grid_buy - grid_sell - transport_fee`. The pricing weight and fee split determine how that benefit is divided. With a positive fee, extreme price weights may give one side a worse rate than the grid even though the energy clearing price itself lies between the grid tariffs.

## Technical structure

```text
grid-link/
├── backend/
│   ├── app/
│   │   ├── main.py          API routes and application lifecycle
│   │   ├── models.py        Participant and market input validation
│   │   ├── database.py      SQLite persistence and Supabase REST access
│   │   └── engine.py        Interval allocation and bill calculation
│   ├── supabase/
│   │   ├── migrations/     Hosted database schema
│   │   ├── functions/      Clearing and participant forwarding functions
│   │   ├── config.toml     Function configuration
│   │   └── schedule.sql    Optional quarter-hour scheduler
│   ├── test_prototype.py    Runnable accounting and API checks
│   ├── requirements.txt    Dependency ranges
│   └── requirements.lock.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx         Page routing, session state, and shared settings
│   │   ├── index.css       Design tokens and responsive styling
│   │   └── main.jsx        React entry point
│   └── index.html          HTML entry point
├── public/                 Static assets
├── vite.config.js          Build configuration and API proxy
├── package.json            Frontend dependencies and npm scripts
├── package-lock.json       Locked frontend dependency versions
├── dev.cmd                 Windows launcher entry point
├── dev.ps1                 Local process startup and logging
└── README.md
```

The frontend requests data from `/api`. During development, Vite proxies those requests to FastAPI on port 8000. FastAPI validates inputs, reads the community and settings from storage, and calls the clearing engine. The returned summary contains rates and aggregate totals, plus only the signed-in member's own interval record.

The clearing engine has no HTTP or database access. It receives participants, market settings, and an interval duration, then returns a result. Keeping this calculation separate allows future inputs from meters or forecasts to use the same accounting without depending on the current signup form or storage backend.

The current frontend uses React state and browser fetch requests. It does not require a routing library or a separate client state service. The storage class contains the two supported storage paths, selected through environment configuration.

## API

| Route | Purpose |
| --- | --- |
| `POST /api/signup` | Register a participant and issue a session |
| `POST /api/login` | Verify credentials and issue a session |
| `POST /api/logout` | Revoke the current session |
| `GET /api/me` | Read the signed-in member's profile |
| `GET /api/community` | Aggregate participant count; no member records |
| `GET /api/clearing-summary` | Calculate the current simulated interval |
| `GET /api/market-settings` | Read saved parameters |
| `PUT /api/market-settings` | Validate and persist parameters |
| `POST /api/clearing-preview` | Calculate with supplied parameters without saving |
| `POST /api/clearing-run` | Persist one immutable snapshot per UTC quarter-hour; requires `x-clearing-token` |
| `GET /api/health` | Storage and simulation status |

The dashboard refreshes every 30 seconds while no settings are being edited. GET/preview calculations do not create settlement history. Local scheduled execution is disabled by default; the protected clearing endpoint is ready for a scheduler.

The clearing summary includes the saved or preview settings, gross clearing price, effective buying and selling rates, fee shares, trade eligibility, totals, and the aggregate participant count. Visitors receive no participant rows; an authenticated member receives only their own row. It also identifies the storage mode, marks the result as a simulation, and includes the UTC interval start. The frontend displays interval times in the browser's local time zone.

Invalid participant or settings submissions return HTTP 422. Duplicate participant names return HTTP 409. The snapshot endpoint returns HTTP 403 if its configured secret is missing or incorrect. A Supabase HTTP failure is reported as HTTP 503 with a database-unavailable message.

## Persistence and clearing snapshots

Local storage contains three tables: `participants`, `market_settings`, and `clearing_events`. Participant rows and the shared settings remain available after a process restart. Browser local storage holds the session token and account identifiers; it does not store the authoritative community or pricing settings.

Viewing a dashboard summary calculates the interval from the current inputs. Refreshing it does not accumulate energy usage over time, generate an invoice, or settle a bill. Without changing demand or production assumptions, repeated intervals have the same modeled energy quantities even as their time labels advance.

The separate clearing-run endpoint stores a snapshot under the current UTC quarter-hour. The first stored result for that interval is retained when the endpoint is called again, including if settings have subsequently changed. This prevents a scheduler retry from overwriting the recorded snapshot or creating a second event for the same slot.

Snapshot persistence is implemented, but the dashboard does not yet provide historical charts or a snapshot browser. The local launcher does not start a scheduler.

## Connect Supabase later

1. Apply `backend/supabase/migrations/001_gridlink.sql` in the project's SQL editor or through Supabase CLI migrations. It creates participants, market settings, and clearing snapshots with RLS and server-only access.
2. Set `SUPABASE_URL` and `SUPABASE_SECRET_KEY` in the backend environment. A legacy `SUPABASE_SERVICE_ROLE_KEY` is also supported. Restart the backend. Keys stay on the server. `.env.example` is a reference; the app reads process environment variables.
3. Existing local rows are not copied automatically. Signups write directly to Supabase once it is connected. Supabase starts empty.
4. For scheduled snapshots, host the backend at an HTTPS URL and set `CLEARING_TOKEN` there. Deploy `clearing` from `backend/supabase`, with `BACKEND_URL` and the same `CLEARING_TOKEN` as function secrets. The function authenticates its secret header; JWT verification is disabled only for this internal job endpoint.
5. Store `project_url` and `gridlink_clearing_token` in Supabase Vault, then run `backend/supabase/schedule.sql` to invoke clearing every 15 minutes. Duplicate requests retain the first snapshot for the slot. This follows [Supabase's scheduling workflow](https://supabase.com/docs/guides/functions/schedule-functions).

The optional `participant-sync` function accepts a participant payload from an internal source, checks the same secret header, and forwards it through backend validation. It does not copy the local database or update existing members.

Supabase functions and SQL are included for setup; they have not been deployed or tested against a live project. Public deployment needs participant authentication and authorization for changing shared market settings. The local prototype binds to loopback and uses a shared demo community.

## Future EV charging functionality

`backend/app/engine.py` is a pure clearing function, separate from storage, HTTP, and UI. It accepts participant loads, market settings, and an interval duration. An EV planner can later supply forecasts and charging loads per interval, then compare total charging costs against grid rates using this engine. Vehicle constraints, meter readings, forecasts, and multi-interval scheduling are not implemented yet.

The intended extension is to let a driver specify how much energy they need and when the vehicle must be ready. A planner could compare the available charging intervals, account for expected local solar and tariffs, and suggest a schedule with a lower modeled cost than charging entirely at the standard grid rate.

That feature would need additional inputs:

- Required charging energy or battery target, together with the vehicle's current charge.
- Arrival time, departure deadline, and the intervals when the vehicle is connected.
- Charger power limits and charging efficiency assumptions.
- Forecasts for community production, ordinary demand, and applicable tariffs.
- A way to allocate or reserve local supply when several vehicles want the same interval.

The planner would convert a proposed charging schedule into additional consumer load for each interval and evaluate it through the clearing engine. It would then compare the schedule's full cost, including the modeled transport fee and any grid energy, with a grid-tariff benchmark.

Adding forecasts and evaluating a schedule would require extending the input model; the existing clearing function alone does not optimize charging time. A lower charging price would depend on available supply, tariff assumptions, the transport split, and the driver's constraints. The current prototype does not promise an EV discount or send commands to a charger.

Other possible extensions include measured consumption and production, multiple communities, historical reporting, participant profiles, and richer allocation policies. These would be separate additions to the working interval model.

## Battery simulator

The battery simulator is retained as research code/API and is no longer rendered on the member-facing site. It compares no storage, night-only scheduling and a day-ahead battery optimiser using the collected Romanian prices and weather. It also compares calendar, local-weather and local-plus-coastal price estimates, with all resulting schedules billed at actual historical prices.

Research simulations accept a historical date and explicit demand/PV/battery assumptions through `POST /api/battery/simulate`. “Surplus for export” demonstrates storing solar for later sales under an illustrative wholesale-linked export contract. Expand the contract settings to adjust import charges, VAT, export remuneration and connection limits. Results use RON and represent one shared billing meter; the existing community trading screen retains its separate EUR demonstration settings.

Install the updated backend dependencies if using another environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.lock.txt
.\dev.cmd
```

This workspace's prepared `.tools/venv` environment is already updated. If the backend was running before the code changed, restart that project's backend process to load the new endpoints. The local launcher reuses running servers and does not enable automatic Python reload.

The battery screen includes cost comparisons, energy/price/state-of-charge charts, an hourly schedule and an optional current 48-hour weather outlook for six Romanian locations. Forecast price estimates remain experimental. Historical weather-model comparisons use ERA5 reanalysis, so their displayed savings do not establish live forecast performance.

See [the implementation and regional-weather analysis](research/romania/BATTERY_OPTIMISER.md) for the constraints, export strategy, experiment results and the data needed for a national forecast. The new API routes are `GET /api/battery/dataset`, `POST /api/battery/simulate` and `GET /api/battery/weather-outlook`.

The [measured-consumption backtest](research/romania/CONSUMER_BACKTEST.md) uses five published German household meter profiles against the Romanian price/weather dataset. It reports bill reductions, profitable-day rates, price-estimation losses and battery-cost/payback assumptions. Its 6,488 scenario-days passed physical checks; annual ROI is a conditional extrapolation from four sampled seasons, and the replay assumes known demand. Run it with:

```powershell
.\.tools\venv\Scripts\python.exe research/romania/backtest_consumers.py
```

## Battery product scope and shared-storage ROI

Signed-in members have **Account ? A battery for your community**, with automatic measured-data analysis, battery technology/size comparisons, coverage, cash ROI/payback/NPV, both contribution rules and the highest-NPV option. Members do not enter tariffs, demand, solar output, quotes or technical constraints. The system reads measured intervals and the selected community's sourced battery catalogue and analysis configuration. Invitations independently recalculate for the destination including the joining member. Missing data/configuration is reported, with no simulation fallback. Forecast-based ROI remains unconnected. See [setup, formulas and funding fairness](docs/COMMUNITY_BATTERY.md); apply both battery migrations and populate sourced configuration before using the analysis.

Decision, 5 October 2026: GridLink will offer shared community storage only. Buying a personal battery is excluded from the prosumer product and roadmap. Prosumers can join with their PV; membership does not require buying a battery. The simulator already represents shared storage behind one billing meter and has no personal-battery enrolment option.

The [shared community comparison](research/romania/CONSUMER_BACKTEST.md#shared-community-results) and its reproducible ROI calculations remain part of the project. For four homes behind one meter with existing 20 kWp PV, the 10.24 kWh scenario projects 4,728 RON annual energy-bill cash savings, 2.38-year simple payback and +284.05% ten-year undiscounted cash ROI. Without PV, that size projects 2,851 RON annual savings and 4.00-year simple payback. Assumed installed cost is 11,000.42 RON with an existing compatible inverter; operating cost is 100 RON/year and projected savings fade by 2% annually.

These are conditional research results using an illustrative export tariff, known demand and modelled PV over four sampled seasons. They require validation against the community's actual contract, full installed cost and forecast errors. They do not establish returns for separately billed members or guarantee a profitable shared installation.

The [personal-battery study](research/romania/PROSUMER_BATTERY_ROI.md) and [per-design results](research/romania/prosumer-designs.csv) are retained as the research record supporting exclusion. At published base costs, none of its 840 main designs has positive ten-year ROI. A few optimistic multi-day cases recover nominal cost but still have negative NPV at 6%. Personal storage is not an available or planned GridLink offering.

## PV farms and apartment buildings

The [Romanian PV-farm and apartment-building feasibility study](research/romania/PV_FARMS_AND_APARTMENTS.md), checked on 5 October 2026, documents merchant solar cases, producer membership restrictions, licensed-supplier alternatives and the workflow for separately enrolled apartment meters. It distinguishes adopted community rules from the billing draft still under consultation, and explains how tariffs, matching demand, batteries and EV charging affect the business case. The current prototype does not perform real supplier/distributor settlement.

## Current limitations

For a researched comparison of Romanian dynamic prices, weather, battery dispatch and EV charging, see [the Romanian market analysis](research/romania/REPORT.md). It includes 120 historical days, hourly price/weather data and a reproducible battery benchmark. The battery simulator uses these datasets; real battery control remains unimplemented.

- The app uses assumed hourly demand/PV profiles and an advisory weather outlook. The separate research backtest uses public measured German demand, but there are no live participant smart-meter feeds or measured Romanian participant profiles.
- Registration adds a member to the shared simulation. Member profiles and interval bills require a session and are limited to the signed-in member. Administrator permissions for shared market settings are not implemented.
- Saved market settings affect the entire community. The current UI has no role-based restriction on changing them.
- Participants can be added, but the current public API does not offer editing or removal.
- Local allocations are proportional. Community clearing does not model geography, congestion, storage or individual contracts. The separate battery simulator models one shared meter, storage losses and configurable tariff assumptions.
- Bills are interval calculations. There are no monthly invoices, payment processing, taxes, or actual settlement with a utility or network operator.
- Supabase setup files are included, but a hosted project and scheduler are not configured by the local launcher.
- EV charging optimization and control are planned functionality.

The prototype is suitable for demonstrating and tuning the model with sample data. Connecting real participants would require measured inputs, a confirmed tariff and cost model, access controls, and a settlement workflow appropriate to the deployment.

## Check

```powershell
.\.tools\venv\Scripts\python.exe -m unittest discover -s backend -v
# For a standard environment, use .venv\Scripts\python.exe instead.
npm.cmd run build
```

The checks exercise accounting and energy conservation across varied communities, transport splits, empty/night markets, uncompetitive prices, API validation, persistence, preview isolation, and duplicate clearing requests. Battery checks also cover state-of-charge conservation, physical operating limits, fair end-of-day charge, real seasonal days, negative prices, zero capacity, a hand-calculated scheduling example and forecast-provider failure.

The accounting checks verify that locally bought and sold energy agree, total supply balances total demand after grid exchanges, the summed transport payments equal the collected fee, and no member loses money against the benchmark when local trading is enabled. API checks use a temporary database to verify rejected inputs, saved settings after restart, and the difference between a preview and a persisted change.

During the prototype build, the production frontend build and headless browser checks also passed. The browser checks covered consumer and prosumer signup, settings previews, saved settings after reload, zero-solar and uncompetitive scenarios, and desktop/mobile rendering. Runnable automated checks are included in `backend/test_prototype.py`; live Supabase deployment remains unverified.
