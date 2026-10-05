# Community battery planning

Open **Account → A battery for your community** after signing in. The community ledger remains removed. The member sees aggregate community economics and only their own contribution; other members' readings are never returned to the browser.

The initial comparison is scoped to the signed-in member's current community and names it in the results. The view compares LFP, NMC and lead-acid scenarios at nine default capacities (5, 10, 15, 20, 30, 40, 60, 80 and 100 kWh); members can enter up to ten capacities. Equipment cost per kWh, fixed installation/inverter cost, power, efficiency, usable capacity, service life, operating costs, degradation allowance, discount rate and connection limits are editable. Initial values are illustrative assumptions, not product specifications or supplier quotes.

Once sufficient history exists, each comparison highlights the battery with the highest base-case NPV, with ROI, payback and the member's contribution. If no compared battery has positive NPV, the interface explains that keeping no battery is financially preferable under those assumptions. The full size/type table and individual projections remain available.

## Measurement and prediction boundaries

The existing clearing snapshots and SQL seed data are simulations. They are **not** measurements of this community. The published German household backtests are research profiles, not this community's meter history either.

Measured comparisons use the new `community_meter_intervals` table. They accept only timezone-aware, aligned, past readings in RON at a verified shared billing meter, with a battery-free baseline. Each interval supplies gross demand, generation and final import/export contract prices. Do not subtract PV twice from an already-net import reading. With no battery, gross demand can be reconstructed as import + generation − export if those feeds share the same meter boundary and timestamps.

The server reads the last 120 days and replays the most recent 30 complete local days. Missing, duplicate, invalid and incomplete days are excluded; 23/25-hour daylight-saving days remain valid. The optimiser accepts hourly or quarter-hour input and resets to the same starting charge at each day's end.

Replayed sample savings appear as soon as a complete day exists. Annual estimates, payback and ROI require 30 complete days. This is a product minimum, not evidence that one month represents a whole year. The annual estimate extends the sample daily average to 365 days. Lower/base/higher sensitivities use 70/100/130% of that saving; they are not statistical confidence intervals or issued price forecasts. Optimal historical dispatch uses known demand and prices and is an upper-bound reference.

If measurements are unavailable, members can explicitly choose **Illustrative planning preview**. It uses current entered community demand and PV capacity with the existing research prices/weather. Demand is flat and the member must confirm a shared-meter assumption. It never becomes measured history.

For separately billed homes or a remote community battery, a supplier/distributor settlement model is needed before applying these returns. Community membership alone does not create behind-the-meter savings.

## Funding: comparing the two rules

| Rule | Implementation | Where it is fairer | Limitation |
| --- | --- | --- | --- |
| Equal shares | Installed cost / current members; equal ownership and allocated savings | Similar usage and equal ownership rights | Small users pay as much as large users |
| Consumption shares | Member gross demand / total measured gross demand over the replay sample; multiply cost and allocated savings by that share | Different levels of usage, with complete readings | Gross demand is not the same as battery benefit; it misses timing and self-consumption |

For example, for a 30,000 RON installation with three members using 10%, 30% and 60% of the community's measured demand, equal contributions are 10,000 RON each; consumption-based contributions are 3,000, 9,000 and 18,000 RON. Consumption shares are generally a better starting point for substantially unequal usage. Equal shares are easier to justify when all members intentionally buy equal ownership and receive equal rights and savings. Neither rule should be called universally equitable without the ownership and benefit agreement.

Measured consumption shares require readings for **every current member in every replayed interval**, adding up to aggregate demand. If anyone's data is missing, the site does not estimate their share. Planning previews use entered demand instead and remain labelled illustrative. New members may need a fresh measurement window.

The interface compares both rules and lets the user choose a personal funding scenario. It does not impose that rule on the group. Costs and savings are allocated by the same selected shares, so member percentage ROI and payback match community ROI/payback; personal amounts differ. The savings allocation is a proposed agreement, not a measured attribution. Before purchase, the group must agree to the installed quote, contribution rule, ownership, maintenance, benefits and exit terms. Ownership shares should be fixed at purchase, not recalculated each time consumption changes. The feature records interest only and does not collect money or purchase equipment.

## Financial calculations

Annual cash savings are the replay's energy-bill savings per sampled day × 365. The optimiser uses a dispatch wear penalty to avoid excessive cycling. Financial cash flows exclude this noncash wear allowance because installed capital cost is already included; subtracting both would count capital wear twice.

For year `y`, net cash is `annual saving × (1 − annual fade)^(y − 1) − annual maintenance`. The projection stops at the shorter of service life and analysis horizon. Payback is the first cumulative cash crossing of installed cost, with interpolation within the year. Cash ROI is `(total net cash − installed cost) / installed cost`; NPV discounts each year's cash and subtracts installed cost. No replacement, financing, subsidy, resale value or price escalation is assumed. Negative returns and no-payback results are shown rather than hidden.

References: [NREL SAM battery modelling](https://sam.nrel.gov/battery-storage.html), [SAM financial models](https://sam.nrel.gov/financial-models.html), [SAM payback definition](https://samrepo.nlr.gov/help/mtf_payback.html). These support the modelling framework; they do not validate the application's illustrative equipment assumptions or community savings.

## Voluntary community switch

Suggestions appear when the member wants a battery and their community has declined or has members who oppose buying one (unless its plan is already approved). Destinations must be interested in or approved for shared storage, have opened admissions, share the member's configured network zone, have a verified shared billing boundary and be explicitly allowed for the member's POD. Approved plans appear before interested plans.

Each invitation independently recalculates the same battery sizes and cost assumptions for the destination **including the joining member**. Measured previews add the member's individual gross demand and, for a prosumer, individual generation to the destination's aggregate history at matching UTC timestamps and interval lengths. The destination's own import/export tariffs are retained. Only complete combined days count towards the 30-day minimum for ROI. Missing individual readings or unmatched histories yield an explanation, not the original community's ROI. Illustrative previews use the destination roster's entered demand/PV plus the joining member instead. Funding shares use the combined roster and demand. These are hypothetical invitation estimates; no synthetic measurements are stored, and viewing them never changes membership.

The member selects **Review invitation and switch**, then explicitly selects **Accept and switch community**. Merely expressing interest or viewing a suggestion never moves membership. The SQL function locks and rechecks the member, both communities and the POD approval. It atomically updates membership, POD community approval and the member's interest, and records the accepted switch. A failed check rolls back the entire operation. The account then reloads its new community. Historical readings stay in their original community.

The receiving operator gives advance admission consent by opening admissions and approving the POD for that destination. This is a membership change; it does not physically relocate a meter, approve a battery purchase or commit a payment.

## Supabase setup

1. Apply [add_community_battery_planning.sql](../backend/supabase/migrations/add_community_battery_planning.sql) after the existing community, participant and approved-POD migrations. This creates private readings, interest and accepted-switch tables and a service-role-only transfer function. It adds community battery metadata and POD admission permissions. It does not seed measured readings or move members.
2. Configure each community's `battery_policy` (`undecided`, `interested`, `declined`, `approved`), `battery_meter_boundary` (`unverified`, `shared_meter`, `separate_meters`) and timezone. An operator must verify the actual shared billing boundary before selecting `shared_meter`.
3. For admissions, configure a verified `network_zone`, enable `battery_accepting_members` at the destination and put its UUID in the member's approved POD's `battery_eligible_communities` array after checking billing/meter compatibility. Without those checks there are no switch suggestions.
4. Set a server-only `METERING_TOKEN` and restart the backend. Use the existing backend Supabase service-role credentials; never give the metering token to browsers.
5. Connect the meter collector to `POST /api/community-battery/measurements` with header `x-metering-token`. Duplicate intervals produce HTTP 409 and are not overwritten. A batch is written in one database request. Readings are not collected automatically by refreshing the dashboard.

Payload shape (values are placeholders; send actual measured values):

```text
{
  "community_id": "<community UUID>",
  "shared_meter_confirmed": true,
  "battery_free_baseline_confirmed": true,
  "readings": [{
    "interval_start": "<aligned ISO timestamp with timezone>",
    "interval_minutes": 15,
    "load_kwh": <gross community demand>,
    "generation_kwh": <community generation>,
    "import_price_ron": <final contract import price per kWh>,
    "export_price_ron": <final export credit per kWh>,
    "member_loads_kwh": {"<member UUID>": <gross demand>, "<member UUID>": <gross demand>},
    "member_generation_kwh": {"<member UUID>": <generation>, "<member UUID>": <generation>}
  }]
}
```

`member_loads_kwh` is optional for current-community ROI but mandatory for measured consumption-based funding and for adding a member to an invitation preview. `member_generation_kwh` is also optional for current-community ROI, but required in the origin's history for a prosumer invitation. If either map is supplied, it must contain exactly all current community members, with finite nonnegative values summing to the corresponding aggregate. Consumers can have zero generation. Both maps are stored in the existing interval JSON; this extension needs no additional migration. The collector's identity and accuracy must be established before accepting its readings; the metering secret only protects ingestion access.

API routes: `GET /api/community-battery`, `POST /api/community-battery/compare`, `POST /api/community-battery/invitation`, `PUT /api/community-battery/interest`, `POST /api/community-battery/switch`, and the server-only measurements endpoint above. Member routes infer community and participant IDs from the authenticated session. Invitation requests specify an eligible destination, which the server checks before reading its data; responses contain only aggregate economics and the requesting member's contribution. Aggregate pricing and settlement requests also follow the signed-in member's community; signup follows the POD's approved community.

## Validation

```powershell
.\.tools\venv\Scripts\python.exe -m unittest discover -s backend -p test_community_battery.py -v
npm.cmd run build
```

The tests exercise real optimiser dispatch, 27 technology/size options, NPV selection, hand-calculated finance, both contribution rules, incomplete/DST data, invitation history alignment and destination tariffs, privacy, community isolation, ingestion authentication and member acceptance. Applying the migration and testing the PostgreSQL transfer transaction against a configured Supabase project remain deployment steps.
