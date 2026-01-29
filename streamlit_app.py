import io

import pandas as pd
import streamlit as st
import altair as alt

import logic
import storage


st.set_page_config(page_title="FIFA Tourney Stats", layout="wide")
storage.ensure_data_files()


def render_create_player():
    st.header("Create Player")
    with st.form("create_player", clear_on_submit=True):
        name = st.text_input("Player name")
        submitted = st.form_submit_button("Add player")
        if submitted:
            ok, msg = logic.add_player(name)
            if ok:
                st.success(f"Added player with id {msg}")
            else:
                st.error(msg)


def render_create_game():
    st.header("Create Game")
    players = logic.list_players()
    if len(players) < 2:
        st.info("Add at least two players first.")
        return

    player_options = {f"{row['name']} ({row['player_id']})": row["player_id"] for _, row in players.iterrows()}
    with st.form("create_game", clear_on_submit=True):
        round_name = st.text_input("Round name (GS, R16, QF, SF, Final)")
        game_label = st.text_input("Game label (ex: GAM1, GBM2)")
        col1, col2 = st.columns(2)
        with col1:
            player_a_label = st.selectbox("Player A", list(player_options.keys()), index=None, placeholder="Select Player A")
        with col2:
            player_b_label = st.selectbox("Player B", list(player_options.keys()), index=None, placeholder="Select Player B")
        allow_draw = st.checkbox("Allow draw", value=True)
        submitted = st.form_submit_button("Create game")
        if submitted:
            if player_a_label is None or player_b_label is None:
                st.error("Please select both Player A and Player B.")
                return
            player_a = player_options[player_a_label]
            player_b = player_options[player_b_label]
            ok, msg = logic.add_game(round_name, game_label, player_a, player_b, allow_draw)
            if ok:
                st.success(f"Created game {msg}")
            else:
                st.error(msg)


def render_enter_stats():
    st.header("Enter Stats for Finished Game")
    players = logic.list_players().set_index("player_id")
    unplayed = logic.get_unplayed_games()
    if unplayed.empty:
        st.info("No unplayed games found.")
        return

    def format_game(row):
        label = row.get("game_label", "") or row["game_id"]
        return f"{row['game_id']} - {row['round_name']} - {label} ({players.loc[row['player_a'], 'name']} vs {players.loc[row['player_b'], 'name']})"

    options = {format_game(row): row for _, row in unplayed.iterrows()}
    selected_label = st.selectbox("Select game", list(options.keys()))
    game = options[selected_label]
    pid_a, pid_b = game["player_a"], game["player_b"]
    name_a, name_b = players.loc[pid_a, "name"], players.loc[pid_b, "name"]

    allow_draw = bool(game["allow_draw"])
    with st.form("enter_stats", clear_on_submit=True):
        st.subheader(f"{name_a}")
        xg_a = st.number_input(f"{name_a} xG", min_value=0.0, value=0.0, step=0.1, key="xg_a")
        goals_a = st.number_input(f"{name_a} goals", min_value=0, value=0, step=1, key="goals_a")
        dribble_a = st.number_input(f"{name_a} dribble success rate (0-100)", min_value=0.0, max_value=100.0, value=0.0, step=0.5, key="ds_a")
        key_passes_a = st.number_input(f"{name_a} key passes", min_value=0, value=0, step=1, key="kp_a")
        interceptions_a = st.number_input(f"{name_a} interceptions", min_value=0, value=0, step=1, key="int_a")
        tackles_a = st.number_input(f"{name_a} tackles", min_value=0, value=0, step=1, key="tkl_a")

        st.subheader(f"{name_b}")
        xg_b = st.number_input(f"{name_b} xG", min_value=0.0, value=0.0, step=0.1, key="xg_b")
        goals_b = st.number_input(f"{name_b} goals", min_value=0, value=0, step=1, key="goals_b")
        dribble_b = st.number_input(f"{name_b} dribble success rate (0-100)", min_value=0.0, max_value=100.0, value=0.0, step=0.5, key="ds_b")
        key_passes_b = st.number_input(f"{name_b} key passes", min_value=0, value=0, step=1, key="kp_b")
        interceptions_b = st.number_input(f"{name_b} interceptions", min_value=0, value=0, step=1, key="int_b")
        tackles_b = st.number_input(f"{name_b} tackles", min_value=0, value=0, step=1, key="tkl_b")

        submitted = st.form_submit_button("Save stats")
        if submitted:
            if goals_a > goals_b:
                result_a, result_b = "win", "loss"
            elif goals_b > goals_a:
                result_a, result_b = "loss", "win"
            else:
                if not allow_draw:
                    st.error("Draws are not allowed for this game. Please enter a decisive score.")
                    return
                result_a, result_b = "draw", "draw"

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
            if ok:
                st.success("Saved stats and marked game as played.")
            else:
                st.error(msg)


def render_leaderboards():
    st.header("Leaderboards")
    boards = logic.compute_leaderboards()
    if not boards:
        st.info("No stats recorded yet.")
        return

    label_map = {
        "most_xg": "Most xG (Most Dangerous)",
        "least_xga": f"Least xGA (Brick Wall) - min {logic.MIN_GAMES_FOR_AVERAGES} games",
        "best_dribbles": f"Best Dribble Success (Entertainer) - min {logic.MIN_GAMES_FOR_AVERAGES} games",
        "key_passes": "Most Key Passes (Maestro)",
        "gatekeeper": "Most Interceptions + Tackles (Gatekeeper)",
    }
    for key, label in label_map.items():
        st.subheader(label)
        if key not in boards or boards[key].empty:
            st.write("No data.")
            continue
        st.dataframe(boards[key])


def render_visualizations():
    st.header("Tournament Insights")
    insights = logic.tournament_insights()
    if not insights:
        st.info("No stats recorded yet.")
        return

    if "avg_xg_by_round" in insights:
        st.subheader("Average xG per game by round")
        round_df = insights["avg_xg_by_round"]
        st.line_chart(round_df.set_index("round_name")["avg_xg_per_game"])


    if "goals_minus_xg_under" in insights or "goals_minus_xg_over" in insights:
        st.subheader("Goals minus xG (under/over performance)")
        col1, col2 = st.columns(2)
        if "goals_minus_xg_under" in insights:
            with col1:
                st.markdown("**Top 5 UNDERperformers (lowest Goals - xG)**")
                df_under = insights["goals_minus_xg_under"]
                chart_under = alt.Chart(df_under).mark_bar(color="red").encode(
                    x=alt.X("name:N", sort="y", title="Player"),
                    y=alt.Y("goals_minus_xg:Q", title="Goals - xG"),
                    tooltip=["name", "goals_total", "total_xg", "goals_minus_xg"]
                ).properties(height=300)
                st.altair_chart(chart_under, use_container_width=True)

        if "goals_minus_xg_over" in insights:
            with col2:
                st.markdown("**Top 5 OVERperformers (highest Goals - xG)**")
                df_over = insights["goals_minus_xg_over"]
                chart_over = alt.Chart(df_over).mark_bar(color="green").encode(
                    x=alt.X("name:N", sort="-y", title="Player"),
                    y=alt.Y("goals_minus_xg:Q", title="Goals - xG"),
                    tooltip=["name", "goals_total", "total_xg", "goals_minus_xg"]
                ).properties(height=300)
                st.altair_chart(chart_over, use_container_width=True)

    if "scatter_data" in insights:
        st.divider()
        st.subheader("Performance Analysis")
        df_scatter = insights["scatter_data"]
        col_s1, col_s2 = st.columns(2)

        with col_s1:
            st.markdown("     **xG vs. xGA (Above the line = Expected to win)**")
            chart_xg_xga = alt.Chart(df_scatter).mark_circle(size=150).encode(
                x=alt.X("xga:Q", title="Total xGA (Against)"),
                y=alt.Y("xg:Q", title="Total xG (Attacking)"),
                color=alt.value("#1f77b4"),
                tooltip=["name", "xg", "xga"]
            ).interactive().properties(height=400)

            max_val = float(max(df_scatter["xg"].max(), df_scatter["xga"].max(), 1))
            line_data = pd.DataFrame({"x": [0, max_val], "y": [0, max_val]})
            line = alt.Chart(line_data).mark_line(
                color="gray", 
                strokeDash=[5, 5], 
                opacity=0.5,
                strokeWidth=4
            ).encode(
                x="x:Q",
                y="y:Q"
            )
            st.altair_chart(chart_xg_xga + line, use_container_width=True)

        with col_s2:
            st.markdown("     **xGA vs. Defensive Action (Do high defensive actions lead to less xG Conceded?**")
            chart_def = alt.Chart(df_scatter).mark_circle(size=150).encode(
                x=alt.X("defensive_actions:Q", title="Total Defensive Actions (Tackles + Ints)"),
                y=alt.Y("xga:Q", title="Total xGA (Against)"),
                color=alt.value("#ff7f0e"),
                tooltip=["name", "defensive_actions", "xga"]
            ).interactive().properties(height=400)
            st.altair_chart(chart_def, use_container_width=True)

        st.divider()
        st.subheader("Attacking Efficiency")
        df_scatter = insights["scatter_data"]
        
        col_s3, col_s4 = st.columns(2)

        with col_s3:
            st.markdown("     **Goals vs. xG (Does xG actually predict goals?)**")
            max_g_xg = float(max(df_scatter["goals"].max(), df_scatter["xg"].max(), 1))
            line_data_goals = pd.DataFrame({"x": [0, max_g_xg], "y": [0, max_g_xg]})

            scatter_goals = alt.Chart(df_scatter).mark_circle(size=150).encode(
                x=alt.X("xg:Q", title="Expected Goals (xG)"),
                y=alt.Y("goals:Q", title="Actual Goals"),
                color=alt.value("#27ae60"),
                tooltip=["name", "goals", "xg"]
            )

            goal_line = alt.Chart(line_data_goals).mark_line(
                color="gray", strokeDash=[5, 5], strokeWidth=3, opacity=0.7
            ).encode(x="x:Q", y="y:Q")

            st.altair_chart((scatter_goals + goal_line).interactive(), use_container_width=True)

        with col_s4:
            st.markdown("     **xG vs. Key Passes (Does passing ability predict xG?)**")
            chart_kp = alt.Chart(df_scatter).mark_circle(size=150).encode(
                x=alt.X("key_passes:Q", title="Key Passes"),
                y=alt.Y("xg:Q", title="Total xG"),
                color=alt.value("#8e44ad"),
                tooltip=["name", "key_passes", "xg"]
            ).interactive()
            st.altair_chart(chart_kp, use_container_width=True)
            


def render_exports():
    st.header("Exports")
    agg = logic.aggregate_player_stats()
    boards = logic.compute_leaderboards()
    if agg.empty:
        st.info("No stats to export.")
        return

    player_buffer = io.StringIO()
    agg.to_csv(player_buffer, index=False)
    st.download_button("Download player summary CSV", player_buffer.getvalue(), file_name="player_summary.csv")

    rows = []
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
    lb_df = pd.DataFrame(rows)
    lb_buffer = io.StringIO()
    lb_df.to_csv(lb_buffer, index=False)
    st.download_button("Download leaderboards CSV", lb_buffer.getvalue(), file_name="leaderboards.csv")


def render_bracket():
    st.header("Tournament Bracket")
    games = logic.get_games_with_results()
    
    if games.empty:
        st.info("No games created yet. Go to 'Players & Games' to add some.")
        return

    # Knockout Rounds
    st.subheader("Knockout Stage")
    knockout_rounds = ["R16", "QF", "SF", "Final"]
    cols = st.columns(len(knockout_rounds))

    for i, round_name in enumerate(knockout_rounds):
        with cols[i]:
            st.markdown(f"### {round_name}")
            round_games = games[games["round_name"] == round_name]
            if round_games.empty:
                st.caption(f"No {round_name} matches.")
            else:
                for _, row in round_games.iterrows():
                    with st.container(border=True):
                        score_a = int(row["score_a"]) if pd.notnull(row["score_a"]) else "?"
                        score_b = int(row["score_b"]) if pd.notnull(row["score_b"]) else "?"
                        
                        # Highlight winner if game was played
                        name_a = row["name_a"]
                        name_b = row["name_b"]
                        if pd.notnull(row["score_a"]):
                            if row["score_a"] > row["score_b"]:
                                name_a = f"**{name_a}** 🏆"
                            elif row["score_b"] > row["score_a"]:
                                name_b = f"**{name_b}** 🏆"

                        st.markdown(f"{name_a}  \n`{score_a}`")
                        st.markdown(f"{name_b}  \n`{score_b}`")
                        st.caption(f"Label: {row['game_label']}")


def main():
    st.title("FIFA Tourney Stats")
    tab1, tab2, tab_bracket, tab3, tab4, tab5 = st.tabs(
        ["Players & Games", "Enter Stats", "Bracket", "Leaderboards", "Visualizations", "Exports"]
    )
    with tab1:
        render_create_player()
        st.divider()
        render_create_game()
    with tab2:
        render_enter_stats()
    with tab_bracket:
        render_bracket()
    with tab3:
        render_leaderboards()
    with tab4:
        render_visualizations()
    with tab5:
        render_exports()


if __name__ == "__main__":
    main()
