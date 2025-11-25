# FIFA Tourney Stats

A simple 1v1 tournament tracker with a CLI and Streamlit UI. Stats are stored in Azure Blob Storage (CSV blobs) so multiple users can update a shared dataset.

## Features
- Create players and games (round + game label) with draw option.
- Enter per-game stats (xG, goals, dribble success rate, key passes, interceptions, tackles, result).
- Leaderboards: Most xG, Least xGA, Best Dribble Success, Most Key Passes, Most Defensive Actions (with tie-breakers and min-games rules).
- Tournament insights: average xG per round/stage, goals minus xG over/under performance tables.
- Exports: player summaries and leaderboard snapshots.

## Setup
1) Install dependencies in your venv (add `azure-storage-blob`, `pandas`, `streamlit` if not already present).
2) Create an Azure Storage container and three blobs with headers:
   - `players.csv`: `player_id,name,created_at`
   - `games.csv`: `game_id,round_name,game_label,player_a,player_b,allow_draw,played_at`
   - `stats.csv`: `game_id,player_id,xg,xga,goals,dribble_success,key_passes,interceptions,tackles,result`
3) Set secrets (do **not** commit these):
   - `AZURE_CONNECTION_STRING` = your storage account connection string
   - `AZURE_CONTAINER` = your container name (e.g., `fifa-stats`)
   Locally, use `.streamlit/secrets.toml` (gitignored) or environment variables. On Streamlit Cloud, paste them into the Secrets UI.

## Run
- CLI: `venv/bin/python main.py`
- Streamlit: `venv/bin/streamlit run streamlit_app.py`

## Notes
- Storage backend is Azure-only by design; missing env/secrets will raise at startup.
- Forms clear on submit to make repeated entry easier.
- Under/over performance shows the top 5 underperformers and top 5 overperformers (Goals - xG).
