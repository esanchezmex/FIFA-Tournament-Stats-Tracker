import os
from datetime import datetime
from typing import Dict, List, Tuple

import pandas as pd

import storage

MIN_GAMES_FOR_AVERAGES = 4


def list_players() -> pd.DataFrame:
    storage.ensure_data_files()
    players = storage.load_players()
    return players.sort_values("name")


def list_games() -> pd.DataFrame:
    storage.ensure_data_files()
    return storage.load_games()


def get_games_with_results() -> pd.DataFrame:
    games = list_games()
    stats = list_stats()
    players = list_players().set_index("player_id")

    if games.empty:
        return pd.DataFrame()

    # Create a scores dataframe from stats
    # Each game has 2 entries in stats
    if not stats.empty:
        scores = stats.groupby("game_id").apply(
            lambda x: pd.Series({
                "score_a": x[x["player_id"] == games.set_index("game_id").loc[x.name, "player_a"]]["goals"].values[0] if not x[x["player_id"] == games.set_index("game_id").loc[x.name, "player_a"]].empty else None,
                "score_b": x[x["player_id"] == games.set_index("game_id").loc[x.name, "player_b"]]["goals"].values[0] if not x[x["player_id"] == games.set_index("game_id").loc[x.name, "player_b"]].empty else None,
            })
        ).reset_index()
        games = games.merge(scores, on="game_id", how="left")
    else:
        games["score_a"] = None
        games["score_b"] = None

    # Add player names
    games["name_a"] = games["player_a"].map(players["name"])
    games["name_b"] = games["player_b"].map(players["name"])

    return games


def list_stats() -> pd.DataFrame:
    storage.ensure_data_files()
    return storage.load_stats()


def add_player(name: str) -> Tuple[bool, str]:
    players = list_players()
    normalized = name.strip().lower()
    if not normalized:
        return False, "Name cannot be empty."
    if any(players["name"].str.lower() == normalized):
        return False, "Player already exists."
    player_id = storage.next_id(players, "player_id", "P")
    new_row = {"player_id": player_id, "name": name.strip(), "created_at": datetime.utcnow().isoformat()}
    updated = pd.concat([players, pd.DataFrame([new_row])], ignore_index=True)
    storage.save_players(updated)
    return True, player_id


def add_game(round_name: str, game_label: str, player_a: str, player_b: str, allow_draw: bool) -> Tuple[bool, str]:
    players = list_players()
    if player_a == player_b:
        return False, "Players must be different."
    if not round_name.strip():
        return False, "Round name cannot be empty."
    if not game_label.strip():
        return False, "Game label cannot be empty."
    if player_a not in set(players["player_id"]) or player_b not in set(players["player_id"]):
        return False, "Invalid player id(s)."
    games = list_games()
    game_id = storage.next_id(games, "game_id", "G")
    new_row = {
        "game_id": game_id,
        "round_name": round_name.strip(),
        "game_label": game_label.strip(),
        "player_a": player_a,
        "player_b": player_b,
        "allow_draw": allow_draw,
        "played_at": "",
    }
    updated = pd.concat([games, pd.DataFrame([new_row])], ignore_index=True)
    storage.save_games(updated)
    return True, game_id


def get_unplayed_games() -> pd.DataFrame:
    games = list_games()
    stats = list_stats()
    played_ids = set(stats["game_id"].unique())
    mask = ~games["game_id"].isin(played_ids)
    return games[mask]


def record_game_stats(game_id: str, entries: List[Dict]) -> Tuple[bool, str]:
    games = list_games()
    match = games[games["game_id"] == game_id]
    if match.empty:
        return False, "Game not found."
    if len(entries) != 2:
        return False, "Exactly two player entries are required."

    stats_df = list_stats()
    if any(stats_df["game_id"] == game_id):
        return False, "Stats already recorded for this game."

    # Enforce player ids match the scheduled game
    row = match.iloc[0]
    expected_players = {row["player_a"], row["player_b"]}
    provided_players = {e.get("player_id") for e in entries}
    if expected_players != provided_players:
        return False, "Entries must match the two players scheduled for this game."

    # Enforce draw rule
    allow_draw = bool(row["allow_draw"])
    results = {e.get("result") for e in entries}
    if not allow_draw and "draw" in results:
        return False, "Draws are not allowed for this game."

    # Ensure xGA matches opponent xG
    first, second = entries
    first["xga"] = second["xg"]
    second["xga"] = first["xg"]

    # Normalize numeric fields
    for entry in entries:
        entry["dribble_success"] = float(entry.get("dribble_success", 0) or 0)
        entry["xg"] = float(entry.get("xg", 0) or 0)
        entry["goals"] = int(entry.get("goals", 0) or 0)
        entry["key_passes"] = int(entry.get("key_passes", 0) or 0)
        entry["interceptions"] = int(entry.get("interceptions", 0) or 0)
        entry["tackles"] = int(entry.get("tackles", 0) or 0)

    stats_df = pd.concat([stats_df, pd.DataFrame(entries)], ignore_index=True)
    storage.save_stats(stats_df)

    games.loc[games["game_id"] == game_id, "played_at"] = datetime.utcnow().isoformat()
    storage.save_games(games)
    return True, "Saved stats."


def aggregate_player_stats() -> pd.DataFrame:
    players = list_players()
    stats = list_stats()
    if stats.empty:
        return pd.DataFrame()

    numeric_cols = ["xg", "xga", "goals", "dribble_success", "key_passes", "interceptions", "tackles"]
    for col in numeric_cols:
        stats[col] = pd.to_numeric(stats[col], errors="coerce").fillna(0)

    stats["def_actions"] = stats["interceptions"] + stats["tackles"]
    stats["win_flag"] = (stats["result"] == "win").astype(int)
    stats["draw_flag"] = (stats["result"] == "draw").astype(int)
    stats["loss_flag"] = (stats["result"] == "loss").astype(int)

    grouped = stats.groupby("player_id").agg(
        games_played=("game_id", "nunique"),
        wins=("win_flag", "sum"),
        draws=("draw_flag", "sum"),
        losses=("loss_flag", "sum"),
        total_xg=("xg", "sum"),
        avg_xga=("xga", "mean"),
        dribble_success_avg=("dribble_success", "mean"),
        goals_total=("goals", "sum"),
        key_passes_total=("key_passes", "sum"),
        interceptions_total=("interceptions", "sum"),
        tackles_total=("tackles", "sum"),
        def_actions_total=("def_actions", "sum"),
    ).reset_index()

    merged = grouped.merge(players, on="player_id", how="left")
    return merged


def _sort_with_tiebreakers(df: pd.DataFrame, primary: str, ascending: bool = False) -> pd.DataFrame:
    if df.empty:
        return df
    return df.sort_values(
        by=[primary, "games_played", "wins"],
        ascending=[ascending, False, False],
    )


def compute_leaderboards() -> Dict[str, pd.DataFrame]:
    agg = aggregate_player_stats()
    boards: Dict[str, pd.DataFrame] = {}
    if agg.empty:
        return boards

    boards["most_xg"] = _sort_with_tiebreakers(agg, "total_xg", ascending=False)[
        ["player_id", "name", "total_xg", "games_played", "wins"]
    ]

    filtered = agg[agg["games_played"] >= MIN_GAMES_FOR_AVERAGES]
    boards["least_xga"] = _sort_with_tiebreakers(filtered, "avg_xga", ascending=True)[
        ["player_id", "name", "avg_xga", "games_played", "wins"]
    ]

    boards["best_dribbles"] = _sort_with_tiebreakers(filtered, "dribble_success_avg", ascending=False)[
        ["player_id", "name", "dribble_success_avg", "games_played", "wins"]
    ]

    boards["key_passes"] = _sort_with_tiebreakers(agg, "key_passes_total", ascending=False)[
        ["player_id", "name", "key_passes_total", "games_played", "wins"]
    ]

    boards["gatekeeper"] = _sort_with_tiebreakers(agg, "def_actions_total", ascending=False)[
        ["player_id", "name", "def_actions_total", "games_played", "wins"]
    ]
    return boards


def tournament_insights() -> Dict[str, pd.DataFrame]:
    """Aggregate tournament-wide stats for visualization tables."""
    insights: Dict[str, pd.DataFrame] = {}
    games = list_games()
    stats = list_stats()
    if games.empty or stats.empty:
        return insights

    # Per-game xG totals
    stats["xg"] = pd.to_numeric(stats["xg"], errors="coerce").fillna(0)
    game_totals = stats.groupby("game_id").agg(total_xg=("xg", "sum")).reset_index()
    game_totals = game_totals.merge(games[["game_id", "round_name", "allow_draw"]], on="game_id", how="left")

    # Average xG per game by round
    # Enforce order: GS -> R16 -> QF -> SF -> Final
    round_order = ["GS", "R16", "QF", "SF", "Final"]
    round_df = (
        game_totals.groupby("round_name")
        .agg(games=("game_id", "count"), avg_xg_per_game=("total_xg", "mean"))
        .reset_index()
    )
    # Order by category
    round_df["round_name"] = pd.Categorical(round_df["round_name"], categories=round_order, ordered=True)
    round_df = round_df.dropna(subset=["round_name"]).sort_values("round_name")
    
    insights["avg_xg_by_round"] = round_df


    # Goals - xG per player (under/over performance)
    agg = aggregate_player_stats()
    if not agg.empty:
        perf = agg.copy()
        perf["goals_minus_xg"] = perf["goals_total"] - perf["total_xg"]
        perf = perf[["player_id", "name", "goals_total", "total_xg", "goals_minus_xg", "games_played", "wins"]]
        perf_sorted = perf.sort_values("goals_minus_xg")
        insights["goals_minus_xg_under"] = perf_sorted.head(5)
        insights["goals_minus_xg_over"] = perf_sorted.tail(5).sort_values("goals_minus_xg", ascending=False)

    return insights


def export_summaries() -> str:
    agg = aggregate_player_stats()
    boards = compute_leaderboards()
    if agg.empty:
        return "No stats to export."
    out_dir = os.path.join("data", "exports")
    os.makedirs(out_dir, exist_ok=True)
    agg.to_csv(os.path.join(out_dir, "player_summary.csv"), index=False)

    rows: List[Dict[str, str]] = []
    for key, df in boards.items():
        for _, row in df.iterrows():
            rows.append(
                {
                    "category": key,
                    "player_id": row["player_id"],
                    "name": row["name"],
                    "value": row[df.columns[2]],
                    "games_played": row["games_played"],
                    "wins": row["wins"],
                }
            )
    lb_path = os.path.join(out_dir, "leaderboards.csv")
    pd.DataFrame(rows).to_csv(lb_path, index=False)
    return f"Exported to {out_dir}"
