import logic
import storage


def input_non_empty(prompt: str) -> str:
    while True:
        val = input(prompt).strip()
        if val:
            return val
        print("Please enter a value.")


def input_float(prompt: str, allow_zero: bool = True) -> float:
    while True:
        raw = input(prompt).strip()
        try:
            val = float(raw)
            if not allow_zero and val <= 0:
                print("Value must be greater than zero.")
                continue
            if val < 0:
                print("Value must be non-negative.")
                continue
            return val
        except ValueError:
            print("Please enter a number.")


def input_int(prompt: str) -> int:
    while True:
        raw = input(prompt).strip()
        try:
            val = int(raw)
            if val < 0:
                print("Value must be non-negative.")
                continue
            return val
        except ValueError:
            print("Please enter a whole number.")


def choose_player(prompt: str) -> str:
    players = logic.list_players()
    if players.empty:
        print("No players available.")
        return ""
    print("Players:")
    for _, row in players.iterrows():
        print(f"{row['player_id']}: {row['name']}")
    while True:
        choice = input_non_empty(prompt)
        if any(players["player_id"] == choice):
            return choice
        print("Invalid player id.")


def create_player() -> None:
    name = input_non_empty("Player name: ")
    ok, msg = logic.add_player(name)
    print("Added player with id " + msg if ok else msg)


def create_game() -> None:
    players = logic.list_players()
    if len(players) < 2:
        print("Need at least two players to create a game.")
        return
    round_name = input_non_empty("Round name (ex: Group Stage, QF, SF, Final): ")
    game_label = input_non_empty("Game label (ex: Group A - match 1): ")
    player_a = choose_player("Select player A by id: ")
    if not player_a:
        return
    while True:
        player_b = choose_player("Select player B by id: ")
        if not player_b:
            return
        if player_b != player_a:
            break
        print("Players must be different.")
    allow_draw_input = input("Allow draw? (y/n) ").strip().lower() or "y"
    allow_draw = allow_draw_input.startswith("y")
    ok, msg = logic.add_game(round_name, game_label, player_a, player_b, allow_draw)
    print(f"Created game {msg}." if ok else msg)


def select_unplayed_game():
    unplayed = logic.get_unplayed_games()
    if unplayed.empty:
        print("No unplayed games found.")
        return None
    print("Unplayed games:")
    for _, row in unplayed.iterrows():
        label = row.get("game_label", "") or row["game_id"]
        print(f"{row['game_id']}: {row['round_name']} - {label} ({row['player_a']} vs {row['player_b']})")
    while True:
        choice = input_non_empty("Select game id: ")
        match = unplayed[unplayed["game_id"] == choice]
        if not match.empty:
            return match.iloc[0].to_dict()
        print("Invalid game id.")


def enter_game_stats() -> None:
    game = select_unplayed_game()
    if not game:
        return
    players = logic.list_players().set_index("player_id")
    pid_a, pid_b = game["player_a"], game["player_b"]
    name_a, name_b = players.loc[pid_a, "name"], players.loc[pid_b, "name"]
    allow_draw = bool(game["allow_draw"])
    print(f"Entering stats for {game['game_id']} - {name_a} vs {name_b}")

    xg_a = input_float(f"{name_a} xG: ")
    xg_b = input_float(f"{name_b} xG: ")

    goals_a = input_int(f"{name_a} goals: ")
    goals_b = input_int(f"{name_b} goals: ")

    dribble_a = input_float(f"{name_a} dribble success rate (0-100): ")
    dribble_b = input_float(f"{name_b} dribble success rate (0-100): ")

    key_passes_a = input_int(f"{name_a} key passes: ")
    key_passes_b = input_int(f"{name_b} key passes: ")

    interceptions_a = input_int(f"{name_a} interceptions: ")
    interceptions_b = input_int(f"{name_b} interceptions: ")

    tackles_a = input_int(f"{name_a} tackles: ")
    tackles_b = input_int(f"{name_b} tackles: ")

    result_option = ""
    valid_results = ["a", "b"] + (["d"] if allow_draw else [])
    while result_option not in valid_results:
        draw_text = "/d for draw" if allow_draw else ""
        result_option = input(f"Who won? (a for {name_a}, b for {name_b}{draw_text}): ").strip().lower()
    if result_option == "a":
        result_a, result_b = "win", "loss"
    elif result_option == "b":
        result_a, result_b = "loss", "win"
    else:
        result_a = result_b = "draw"

    entries = [
        {
            "game_id": game["game_id"],
            "player_id": pid_a,
            "xg": xg_a,
            "goals": goals_a,
            "dribble_success": dribble_a,
            "key_passes": key_passes_a,
            "interceptions": interceptions_a,
            "tackles": tackles_a,
            "result": result_a,
        },
        {
            "game_id": game["game_id"],
            "player_id": pid_b,
            "xg": xg_b,
            "goals": goals_b,
            "dribble_success": dribble_b,
            "key_passes": key_passes_b,
            "interceptions": interceptions_b,
            "tackles": tackles_b,
            "result": result_b,
        },
    ]

    ok, msg = logic.record_game_stats(game["game_id"], entries)
    print(msg if ok else msg)


def show_leaderboards() -> None:
    boards = logic.compute_leaderboards()
    if not boards:
        print("No stats recorded yet.")
        return
    print("\n--- Leaderboards ---")
    label_map = {
        "most_xg": "Most xG (Most Dangerous)",
        "least_xga": f"Least xGA (Brick Wall) - min {logic.MIN_GAMES_FOR_AVERAGES} games",
        "best_dribbles": f"Best Dribble Success (Entertainer) - min {logic.MIN_GAMES_FOR_AVERAGES} games",
        "key_passes": "Most Key Passes (Maestro)",
        "gatekeeper": "Most Interceptions + Tackles (Gatekeeper)",
    }
    for key, label in label_map.items():
        if key not in boards or boards[key].empty:
            print(f"{label}: no data")
            continue
        print(f"\n{label}")
        df = boards[key].head(10)
        print(df.to_string(index=False))
    print("")


def export_summaries() -> None:
    msg = logic.export_summaries()
    print(msg)


def main() -> None:
    storage.ensure_data_files()
    menu = """
FIFA Tourney Stats CLI
1) Create player
2) Create game and assign players
3) Enter stats for a finished game
4) Show leaderboards
5) Export summary CSVs
6) Quit
Choice: """
    actions = {
        "1": create_player,
        "2": create_game,
        "3": enter_game_stats,
        "4": show_leaderboards,
        "5": export_summaries,
    }
    while True:
        choice = input(menu).strip()
        if choice == "6":
            print("Goodbye.")
            break
        action = actions.get(choice)
        if action:
            action()
        else:
            print("Invalid choice.")


if __name__ == "__main__":
    main()
