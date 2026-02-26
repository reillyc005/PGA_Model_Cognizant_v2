# PGA_Model_Cognizant_v2 (v2-final)

Stable, automation-ready PGA model with:
- Direct DataGolf feeds API (no tool-results paths)
- Raw-response caching (`data/raw/`)
- Deterministic simulation (seeded)
- Guardrails + calibration report every run
- Pre-tournament workflow (no live endpoints)

## Quickstart (PowerShell)
1. Copy `.env.example` → `.env` and set `DATAGOLF_API_KEY` (and optional `WEATHER_API_KEY`).
2. Run:
   ```powershell
   .\run.ps1 -Mode pretournament -Seed 42
   ```

Outputs are written to `out/`.
