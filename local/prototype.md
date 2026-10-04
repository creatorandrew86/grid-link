# GridLink Prototype Specification

### Agent Implementation Prompt

Build a decoupled prototype for **GridLink** with a Python FastAPI backend and a React/Vite frontend styled strictly using `local/designs/ON Energy Design.md`.

**Backend (`backend/` — FastAPI + Supabase):**
1. **DB & Endpoints**: Persist `participants` (id, name, type: `consumer` | `prosumer`, load_kw, solar_kwp) in a community table. Expose `POST /api/signup`, `GET /api/community`, and `GET /api/clearing-summary`.
2. **Supabase Functions (`backend/supabase/`)**: Houses edge functions and migrations for scheduled 15-minute clearing events and participant sync.
3. **Clearing Algorithm (`app/engine.py`)**:
   - Tariffs: $P_{\text{buy}}^{\text{grid}} = €0.30$, $P_{\text{sell}}^{\text{grid}} = €0.08$.
   - Prosumer clearing: $P_{\text{clear}} = P_{\text{sell}} + 0.60 \times (P_{\text{buy}} - P_{\text{sell}})$.
   - Match local solar to community load. Prosumers sell surplus at $P_{\text{clear}}$ (remainder to grid at $P_{\text{sell}}$). Consumers buy community solar at $P_{\text{clear}} + 0.015$ (deficit from grid at $P_{\text{buy}}$).
   - Compute optimized bills vs standard grid benchmark.

**Frontend (`frontend/` — React + Tailwind):**
1. **Landing & Onboarding**: Sign-up flow registering a user as Consumer or Prosumer to the community DB.
2. **Dashboard**: Live market rates ($P_{\text{buy}}$, $P_{\text{sell}}$, $P_{\text{clear}}$), bill optimization comparison (P2P savings/earnings vs grid), and community member ledger.

**Project Structure:**
```
gridlink/
├── backend/
│   ├── app/ (main.py, models.py, database.py, engine.py)
│   ├── supabase/ (functions/, migrations/)
│   └── requirements.txt
└── frontend/
    ├── src/ (App.jsx, components/, index.css)
    └── package.json
```
