# System libraries
import os
from datetime import datetime

# Data libraries
import pandas as pd
import psycopg2

# Visualization Libraries
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import streamlit.components.v1 as components

# Google Cloud Libraries
import firebase_admin
from google.cloud import bigquery
from firebase_admin import firestore
from google.oauth2 import service_account

st.set_page_config(page_title="Overview", layout="wide")

def local_css(file_name):
    with open(file_name) as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

def background_processing():
    # Create API client.
    credentials = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"]
    )

    # Authenticating with Google Cloud.
    client = bigquery.Client(credentials=credentials)
    db = firestore.Client(credentials=credentials)

    # Check to see if firebase app has been initialized.
    if not firebase_admin._apps:
        firebase_admin.initialize_app()

    # ----- BigQuery Connection ----- #
    # Perform query.
    # Uses st.cache_data to only rerun when the query changes or after 10 min.
    @st.cache_data(ttl=600)
    def run_query(query):
        query_job = client.query(query)
        raw_data = query_job.result()
        # Convert to list of dicts. Required for st.experimental_memo to hash the return value.
        data = [dict(data) for data in raw_data]
        return data

    # ----- PostgreSQL Connection ----- #
    # Initialize connection.
    # Uses st.cache_resource to only run once.
    @st.cache_resource
    def init_connection():
        return psycopg2.connect(**st.secrets["postgres"])

    conn = init_connection()

    # Perform query.
    # Uses st.cache_data to only rerun when the query changes or after 10 min.
    @st.cache_data(ttl=600)
    def run_postgres_query(postgres_query):
        with conn.cursor() as cur:
            cur.execute(postgres_query)
            return cur.fetchall()

    min_round_row = run_postgres_query("SELECT MIN(round) FROM rounds;")
    max_round_row = run_postgres_query("SELECT MAX(round) FROM rounds;")

    # Saving the MINIMUM round to a variable.
    min_round_postgres = min_round_row[0]

    # Saving the MAXIMUM round to a variable.
    max_round_postgres = max_round_row[0]

    # Calling variables from toml file.
    locations_table = st.secrets["football_db"]["locations"]
    players_table = st.secrets["football_db"]["players"]
    standings_table = st.secrets["football_db"]["standings"]
    teams_table = st.secrets["football_db"]["teams"]

    # Running SQL query to retrieve data from the following tables:

    # Locations table.
    locations_data = run_query(f"""
        SELECT latitude, longitude, stadium, team
        FROM {locations_table}
        """
    )

    # Players table.
    players_data = run_query(f"""
        SELECT *
        FROM {players_table}
        ORDER BY Goals DESC
        """
    )

    # Standings table.
    standings_data = run_query(f"""
        SELECT Rank, Team, Wins, Draws, Loses, Points, GF, GA, GD
        FROM {standings_table}
        ORDER BY Rank
        """
    )

    # Splitting Standings table to get values to build metric cards.
    status_data = run_query(f"""
        SELECT Rank, Team, Points, Status
        FROM {standings_table}
        ORDER BY Rank
        """
    )

    # Teams table.
    teams_data = run_query(f"""
        SELECT t.team, logo, form, clean_sheets, penalties_scored, penalties_missed, average_goals, win_streak
        FROM {teams_table} AS t
        LEFT JOIN {standings_table} AS s
        ON t.team = s.Team
        ORDER BY s.Rank
        """
    )

    # Creating dataframes from BigQuery tables.
    locations_df = pd.DataFrame(data = locations_data)
    players_df = pd.DataFrame(data = players_data)
    standings_df = pd.DataFrame(data = standings_data)
    status_df = pd.DataFrame(data = status_data)
    teams_df = pd.DataFrame(data = teams_data)

    return locations_df, players_df, standings_df, status_df, teams_df, db, min_round_postgres, max_round_postgres

# Function that holds all elements of display for the dashboard.
def streamlit_app():
    locations_df, players_df, standings_df, status_df, teams_df, db, min_round_postgres, max_round_postgres = background_processing()

    logo = st.secrets["elements"]["logo_image"]

    # Premier League logo.
    col1, col = st.columns((2, 4))
    with st.container():
        col1.image(logo)

    # Title.
    col1, col = st.columns((9, 1))
    with st.container():
        col1.title("Premier League Statistics / 2023-24")

        # Get the current date
        current_date = datetime.now()
        formatted_date = current_date.strftime("%B %dth, %Y")
        st.write(f"{formatted_date}")

    # Tab menu.
    tab1, tab2, tab3 = st.tabs(["Standings", "Statistics", "Fixtures"])

    # --------- Overview Tab ---------
    with tab1:
        
        st.subheader("Top Teams Movement")
        col1, col2, col3, col4, col5 = st.columns(5)

        for col, index in zip([col1, col2, col3, col4, col5], range(5)):
            with col:
                if status_df.iloc[index][3] == "same":
                    status = None
                elif status_df.iloc[index][3] == "down":
                    status = "-down"
                else:
                    status = "up"

                st.metric(
                    label = f"{status_df.iloc[index][1]}", # Teams
                    value = f"Pts: {status_df.iloc[index][2]}", # Points
                    delta = status,
                )

        col1, col2, col3 = st.columns(3)
        with col1:
            penalties_scored_df = pd.DataFrame(
                {
                    "Penalties Scored": [teams_df.iloc[0][4], teams_df.iloc[1][4], teams_df.iloc[2][4], teams_df.iloc[3][4], teams_df.iloc[4][4]],
                    "Team": [teams_df.iloc[0][0], teams_df.iloc[1][0], teams_df.iloc[2][0], teams_df.iloc[3][0], teams_df.iloc[4][0]]
                }
            )


            st.data_editor(
                penalties_scored_df,
                column_config={
                    "Penalties Scored": st.column_config.ProgressColumn(
                        "Penalties Scored",
                        help="The Amount of Penalties Scored by Each Team.",
                        format="%d",
                        min_value=0,
                        max_value=20,
                    ),
                },
                hide_index=True,
                key="penalties_scored"
            )

        with col2:
            average_goals_df = pd.DataFrame(
                {
                    "Average Goals": [teams_df.iloc[0][6], teams_df.iloc[1][6], teams_df.iloc[2][6], teams_df.iloc[3][6], teams_df.iloc[4][6]],
                    "Team": [teams_df.iloc[0][0], teams_df.iloc[1][0], teams_df.iloc[2][0], teams_df.iloc[3][0], teams_df.iloc[4][0]]
                }
            )

            st.data_editor(
                average_goals_df,
                column_config={
                    "Average Goals": st.column_config.ProgressColumn(
                        "Average Goals",
                        help="The Average Goals Scored by Each Team.",
                        format="%f",
                        min_value=0,
                        max_value=20,
                    ),
                },
                hide_index=True,
                key="average_goals"
            )

        with col3:
            win_streak_df = pd.DataFrame(
                {
                    "Win Streak": [teams_df.iloc[0][7], teams_df.iloc[1][7], teams_df.iloc[2][7], teams_df.iloc[3][7], teams_df.iloc[4][7]],
                    "Team": [teams_df.iloc[0][0], teams_df.iloc[1][0], teams_df.iloc[2][0], teams_df.iloc[3][0], teams_df.iloc[4][0]]
                }
            )


            st.data_editor(
                win_streak_df,
                column_config={
                    "Win Streak": st.column_config.ProgressColumn(
                        "Win Streak",
                        help="The Win Streak by Each Team.",
                        format="%d",
                        min_value=0,
                        max_value=15
                    ),
                },
                hide_index=True,
                key="win_streak"
            )

        # Standings table.
        st.subheader("Standings")

        # Standings table.
        st.table(standings_df)

        # List of promotions/demotions for the league.
        st.markdown(
            # '&nbsp' adds a non-breaking space.
            """
                <p style='color:#55A630'>- Champions League</p>
                <p style='color:#0077B6'>- Europa League</p>
                <p style='color:#48cae4'>- Europa Conference League Qualification</p>
                <p style='color:#d00000'>- Relegation</p>
            """,
            unsafe_allow_html=True
        )

        # Social media icons section.
        st.divider()
        st.subheader("Social")

        components.html(
            """
            <script src="https://kit.fontawesome.com/84587c6ecd.js" crossorigin="anonymous"></script>
            <div style="display: flex; flex-direction: row;">
                <a target="_blank" rel="noopener noreferrer" href="https://github.com/digitalghost-dev/"><i class='fa-brands fa-github fa-2x fa-fade' style='color: #000000; padding-right: 1rem'></i></a>
                <a target="_blank" rel="noopener noreferrer" href="https://www.linkedin.com/in/christian-sanchez-nv/"><i class='fa-brands fa-linkedin fa-2x fa-fade' style='color: #000000; padding-right: 1rem'></i></a>
                <a target="_blank" rel="noopener noreferrer" href="https://medium.com/@digitialghost-dev"><i class='fa-brands fa-medium fa-2x fa-fade' style='color: #000000;'></i></a>
            </div>
            """
        )

    # --------- Statistics Tab ---------
    with tab2:
        
        st.subheader("Top 5 Teams")

        col1, col2, col3, col4, col5 = st.columns(5)

        with col1:
            # First top team.
            # st.markdown(f"![Image]({(teams_df.iloc[0][0])})")
            st.markdown(f"<img style='display: block; margin-left: auto; margin-right: auto; width: 150px;' src='{(teams_df.iloc[0][1])}'/>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align: center; padding-top: 0.8rem;'><b>1st / Form (Last 5):</b> {((teams_df.iloc[0][2])[-5:])}</p>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align: center;'><b>Clean Sheets:</b> {(teams_df.iloc[0][3])}</p>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align: center;'><b>Penalties Scored:</b> {(teams_df.iloc[0][4])}</p>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align: center;'><b>Penalties Missed:</b> {(teams_df.iloc[0][5])}</p>", unsafe_allow_html=True)

        with col2:
            # Second top team.
            st.markdown(f"<img style='display: block; margin-left: auto; margin-right: auto; width: 150px;' src='{(teams_df.iloc[1][1])}'/>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align: center; padding-top: 0.8rem;'><b>2nd / Form (Last 5):</b> {((teams_df.iloc[1][2])[-5:])}</p>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align: center;'><b>Clean Sheets:</b> {(teams_df.iloc[1][3])}</p>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align: center;'><b>Penalties Scored:</b> {(teams_df.iloc[1][4])}</p>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align: center;'><b>Penalties Missed:</b> {(teams_df.iloc[1][5])}</p>", unsafe_allow_html=True)

        with col3:
            # Third top team.
            st.markdown(f"<img style='display: block; margin-left: auto; margin-right: auto; width: 150px;' src='{(teams_df.iloc[2][1])}'/>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align: center; padding-top: 0.8rem;'><b>3rd / Form (Last 5):</b> {((teams_df.iloc[2][2])[-5:])}</p>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align: center;'><b>lean Sheets:</b> {(teams_df.iloc[2][3])}</p>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align: center;'><b>Penalties Scored:</b> {(teams_df.iloc[2][4])}</p>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align: center;'><b>Penalties Missed:</b> {(teams_df.iloc[2][5])}</p>", unsafe_allow_html=True)

        with col4:
            # Fourth top team.
            st.markdown(f"<img style='display: block; margin-left: auto; margin-right: auto; width: 150px;' src='{(teams_df.iloc[3][1])}'/>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align: center; padding-top: 0.8rem;'><b>4th / Form (Last 5):</b> {((teams_df.iloc[3][2])[-5:])}</p>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align: center;'><b>lean Sheets:</b> {(teams_df.iloc[3][3])}</p>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align: center;'><b>Penalties Scored:</b> {(teams_df.iloc[3][4])}</p>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align: center;'><b>Penalties Missed:</b> {(teams_df.iloc[3][5])}</p>", unsafe_allow_html=True)

        with col5:
            # Fifth top team.
            st.markdown(f"<img style='display: block; margin-left: auto; margin-right: auto; width: 150px;' src='{(teams_df.iloc[4][1])}'/>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align: center; padding-top: 0.8rem;'><b>5th / Form (Last 5):</b> {((teams_df.iloc[4][2])[-5:])}</p>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align: center;'><b>Clean Sheets:</b> {(teams_df.iloc[4][3])}</p>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align: center;'><b>Penalties Scored:</b> {(teams_df.iloc[4][4])}</p>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align: center;'><b>Penalties Missed:</b> {(teams_df.iloc[4][5])}</p>", unsafe_allow_html=True)

        team_forms = [[], [], [], [], []]

        forms = [teams_df.iloc[0][1], teams_df.iloc[1][1], teams_df.iloc[2][1], teams_df.iloc[3][1], teams_df.iloc[4][1]]

        count = 0
        while count < 5:
            points = 0
            for char in forms[count]:
                if char == "W":
                    points += 3
                elif char == "D":
                    points += 1
                else:
                    points += 0

                team_forms[count].append(points)

            count += 1

        headers = [
            str(standings_df.iloc[0][1]),
            str(standings_df.iloc[1][1]),
            str(standings_df.iloc[2][1]),
            str(standings_df.iloc[3][1]),
            str(standings_df.iloc[4][1]),
        ]

        zipped = list(zip(team_forms[0], team_forms[1], team_forms[2], team_forms[3], team_forms[4]))

        df = pd.DataFrame(zipped, columns=headers)

        st.subheader("")

        st.subheader("Point Progression thoughout the Season")

        st.line_chart(data=df)

        st.subheader("Top 5 Scorers")
        
        col1, col2, col3, col4, col5 = st.columns(5)

        with col1:
            # First top scorer.
            st.markdown(f"<img style='display: block; margin-left: auto; margin-right: auto; width: 150px;' src='{(players_df.iloc[0][5])}'/>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align: center; padding-top: 0.8rem;'><b>{(players_df.iloc[0][0])}</b></p>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align: center;'><b>Goals:</b> {(players_df.iloc[0][1])}</p>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align: center;'><b>Assists:</b> {(players_df.iloc[0][3])}</p>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align: center;'><b>Team:</b> {(players_df.iloc[0][2])}</p>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align: center;'><b>Nationality:</b> {(players_df.iloc[0][4])}</p>", unsafe_allow_html=True)
        
        with col2:
            # Second top scorer.
            st.markdown(f"<img style='display: block; margin-left: auto; margin-right: auto; width: 150px;' src='{(players_df.iloc[1][5])}'/>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align: center; padding-top: 0.8rem;'><b>{(players_df.iloc[1][0])}</b></p>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align: center;'><b>Goals:</b> {(players_df.iloc[1][1])}</p>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align: center;'><b>Assists:</b> {(players_df.iloc[1][3])}</p>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align: center;'><b>Team:</b> {(players_df.iloc[1][2])}</p>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align: center;'><b>Nationality:</b> {(players_df.iloc[1][4])}</p>", unsafe_allow_html=True)

        with col3:
            # Third top scorer.
            st.markdown(f"<img style='display: block; margin-left: auto; margin-right: auto; width: 150px;' src='{(players_df.iloc[2][5])}'/>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align: center; padding-top: 0.8rem;'><b>{(players_df.iloc[2][0])}</b></p>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align: center;'><b>Goals:</b> {(players_df.iloc[2][1])}</p>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align: center;'><b>Assists:</b> {(players_df.iloc[2][3])}</p>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align: center;'><b>Team:</b> {(players_df.iloc[2][2])}</p>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align: center;'><b>Nationality:</b> {(players_df.iloc[2][4])}</p>", unsafe_allow_html=True)

        with col4:
            # Fourth top scorer.
            st.markdown(f"<img style='display: block; margin-left: auto; margin-right: auto; width: 150px;' src='{(players_df.iloc[3][5])}'/>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align: center; padding-top: 0.8rem;'><b>{(players_df.iloc[3][0])}</b></p>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align: center;'><b>Goals:</b> {(players_df.iloc[3][1])}</p>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align: center;'><b>Assists:</b> {(players_df.iloc[3][3])}</p>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align: center;'><b>Team:</b> {(players_df.iloc[3][2])}</p>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align: center;'><b>Nationality:</b> {(players_df.iloc[3][4])}</p>", unsafe_allow_html=True)
            
        with col5:
            # Fifth top scorer.
            st.markdown(f"<img style='display: block; margin-left: auto; margin-right: auto; width: 150px;' src='{(players_df.iloc[4][5])}'/>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align: center; padding-top: 0.8rem;'><b>{(players_df.iloc[4][0])}</b></p>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align: center;'><b>Goals:</b> {(players_df.iloc[4][1])}</p>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align: center;'><b>Assists:</b> {(players_df.iloc[4][3])}</p>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align: center;'><b>Team:</b> {(players_df.iloc[4][2])}</p>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align: center;'><b>Nationality:</b> {(players_df.iloc[4][4])}</p>", unsafe_allow_html=True)

        with st.container():
            st.subheader("")
            st.subheader("Forms for the Rest of the League")

            col1, col2, col3, col4, col5 = st.columns(5)

            with col1:
                st.markdown(f"<img style='display: block; margin-left: auto; margin-right: auto; width: 75px;' src='{(teams_df.iloc[5][0])}'/>", unsafe_allow_html=True)
                st.markdown(f"<p style='text-align: center; padding-top: 0.8rem;'>6th / {((teams_df.iloc[5][1])[-5:])}</p>", unsafe_allow_html=True)

                st.markdown(f"<img style='display: block; margin-left: auto; margin-right: auto; width: 75px;' src='{(teams_df.iloc[10][0])}'/>", unsafe_allow_html=True)
                st.markdown(f"<p style='text-align: center; padding-top: 0.8rem;'>11th / {((teams_df.iloc[10][1])[-5:])}</p>", unsafe_allow_html=True)

                st.markdown(f"<img style='display: block; margin-left: auto; margin-right: auto; width: 75px;' src='{(teams_df.iloc[15][0])}'/>", unsafe_allow_html=True)
                st.markdown(f"<p style='text-align: center; padding-top: 0.8rem;'>16th / {((teams_df.iloc[15][1])[-5:])}</p>", unsafe_allow_html=True)

            with col2:
                st.markdown(f"<img style='display: block; margin-left: auto; margin-right: auto; width: 75px;' src='{(teams_df.iloc[6][0])}'/>", unsafe_allow_html=True)
                st.markdown(f"<p style='text-align: center; padding-top: 0.8rem;'>7th / {((teams_df.iloc[6][1])[-5:])}</p>", unsafe_allow_html=True)

                st.markdown(f"<img style='display: block; margin-left: auto; margin-right: auto; width: 75px;' src='{(teams_df.iloc[11][0])}'/>", unsafe_allow_html=True)
                st.markdown(f"<p style='text-align: center; padding-top: 0.8rem;'>12th / {((teams_df.iloc[11][1])[-5:])}</p>", unsafe_allow_html=True)

                st.markdown(f"<img style='display: block; margin-left: auto; margin-right: auto; width: 75px;' src='{(teams_df.iloc[16][0])}'/>", unsafe_allow_html=True)
                st.markdown(f"<p style='text-align: center; padding-top: 0.8rem;'>17th / {((teams_df.iloc[16][1])[-5:])}</p>", unsafe_allow_html=True)

            with col3:
                st.markdown(f"<img style='display: block; margin-left: auto; margin-right: auto; width: 75px;' src='{(teams_df.iloc[7][0])}'/>", unsafe_allow_html=True)
                st.markdown(f"<p style='text-align: center; padding-top: 0.8rem;'>8th / {((teams_df.iloc[7][1])[-5:])}</p>", unsafe_allow_html=True)

                st.markdown(f"<img style='display: block; margin-left: auto; margin-right: auto; width: 75px;' src='{(teams_df.iloc[12][0])}'/>", unsafe_allow_html=True)
                st.markdown(f"<p style='text-align: center; padding-top: 0.8rem;'>13th / {((teams_df.iloc[12][1])[-5:])}</p>", unsafe_allow_html=True)

                st.markdown(f"<img style='display: block; margin-left: auto; margin-right: auto; width: 75px;' src='{(teams_df.iloc[17][0])}'/>", unsafe_allow_html=True)
                st.markdown(f"<p style='text-align: center; padding-top: 0.8rem;'>18th / {((teams_df.iloc[17][1])[-5:])}</p>", unsafe_allow_html=True)

            with col4:
                st.markdown(f"<img style='display: block; margin-left: auto; margin-right: auto; width: 75px;' src='{(teams_df.iloc[8][0])}'/>", unsafe_allow_html=True)
                st.markdown(f"<p style='text-align: center; padding-top: 0.8rem;'>9th / {((teams_df.iloc[8][1])[-5:])}</p>", unsafe_allow_html=True)

                st.markdown(f"<img style='display: block; margin-left: auto; margin-right: auto; width: 75px;' src='{(teams_df.iloc[13][0])}'/>", unsafe_allow_html=True)
                st.markdown(f"<p style='text-align: center; padding-top: 0.8rem;'>14th / {((teams_df.iloc[13][1])[-5:])}</p>", unsafe_allow_html=True)

                st.markdown(f"<img style='display: block; margin-left: auto; margin-right: auto; width: 75px;' src='{(teams_df.iloc[18][0])}'/>", unsafe_allow_html=True)
                st.markdown(f"<p style='text-align: center; padding-top: 0.8rem;'>19th / {((teams_df.iloc[18][1])[-5:])}</p>", unsafe_allow_html=True)

            with col5:
                st.markdown(f"<img style='display: block; margin-left: auto; margin-right: auto; width: 75px;' src='{(teams_df.iloc[9][0])}'/>", unsafe_allow_html=True)
                st.markdown(f"<p style='text-align: center; padding-top: 0.8rem;'>10th / {((teams_df.iloc[9][1])[-5:])}</p>", unsafe_allow_html=True)

                st.markdown(f"<img style='display: block; margin-left: auto; margin-right: auto; width: 75px;' src='{(teams_df.iloc[14][0])}'/>", unsafe_allow_html=True)
                st.markdown(f"<p style='text-align: center; padding-top: 0.8rem;'>15th / {((teams_df.iloc[14][1])[-5:])}</p>", unsafe_allow_html=True)

                st.markdown(f"<img style='display: block; margin-left: auto; margin-right: auto; width: 75px;' src='{(teams_df.iloc[19][0])}'/>", unsafe_allow_html=True)
                st.markdown(f"<p style='text-align: center; padding-top: 0.8rem;'>20th / {((teams_df.iloc[19][1])[-5:])}</p>", unsafe_allow_html=True)

        # Social media icons section.
        st.divider()
        st.subheader("Social")

        components.html(
            """
            <script src="https://kit.fontawesome.com/84587c6ecd.js" crossorigin="anonymous"></script>
            <div style="display: flex; flex-direction: row;">
                <a target="_blank" rel="noopener noreferrer" href="https://github.com/digitalghost-dev/"><i class='fa-brands fa-github fa-2x fa-fade' style='color: #000000; padding-right: 1rem'></i></a>
                <a target="_blank" rel="noopener noreferrer" href="https://www.linkedin.com/in/christian-sanchez-nv/"><i class='fa-brands fa-linkedin fa-2x fa-fade' style='color: #000000; padding-right: 1rem'></i></a>
                <a target="_blank" rel="noopener noreferrer" href="https://medium.com/@digitialghost-dev"><i class='fa-brands fa-medium fa-2x fa-fade' style='color: #000000;'></i></a>
            </div>
            """
        )

    # --------- Fixtures Tab ---------
    with tab3:

        st.subheader("Fixtures per Round")

        # Looping through each collection to get each round.
        round_count = int(max_round_postgres[0])
        while round_count >= int(min_round_postgres[0]):

            # Function to pull collection and documents.
            def firestore_pull():

                # Calling each document in the collection in ascending order by date.
                collection_ref = db.collection(f'Regular Season - {round_count}')
                query = collection_ref.order_by("date", direction=firestore.Query.ASCENDING)
                results = query.stream()

                # Setting an empty list. This list will contain each fixtures' details that can later be called by referecing its index.
                documents = []

                # Iterating through the query results to get the document ID (ex: 'Manchester City vs Burnley') and its data.
                for doc in results:
                    document_dict = {
                        "id": doc.id,
                        "data": doc.to_dict()
                    }
                    documents.append(document_dict)

                # Retrieving and formatting match date.
                match_date = [datetime.strptime(documents[count]['data']['date'], 
                    '%Y-%m-%dT%H:%M:%S+00:00').strftime('%B %d{}, %Y - %H:%M').format("th" if 4<=int(datetime.strptime(documents[count]['data']['date'], 
                    '%Y-%m-%dT%H:%M:%S+00:00').strftime("%d"))<=20 else {1:"st", 2:"nd", 3:"rd"}.get(int(datetime.strptime(documents[count]['data']['date'], 
                    '%Y-%m-%dT%H:%M:%S+00:00').strftime("%d"))%10, "th")) for count in range(10)]

                # Retrieving away and home goals for each match.
                away_goals = [documents[count]['data']['goals']['away'] for count in range(10)]
                home_goals = [documents[count]['data']['goals']['home'] for count in range(10)]

                # Retrieving away and home team for each match.
                away_team = [documents[count]['data']['teams']['away']['name'] for count in range(10)]
                home_team = [documents[count]['data']['teams']['home']['name'] for count in range(10)]

                # Retrieving away and home logo for each team.
                away_logo = [documents[count]['data']['teams']['away']['logo'] for count in range(10)]
                home_logo = [documents[count]['data']['teams']['home']['logo'] for count in range(10)]

                return match_date, away_goals, home_goals, away_team, home_team, away_logo, home_logo

            # Placing data in an expander.
            with st.expander(f"Round {round_count}"):
                match_date, away_goals, home_goals, away_team, home_team, away_logo, home_logo = firestore_pull()

                count = 0
                while count < 10:

                    # Creating a container for each match.
                    with st.container():
                        col1, col2, col3, col4, col5 = st.columns(5)

                        with col1:
                            st.write("")

                        # Home teams
                        with col2:
                            st.markdown(f"<h3 style='text-align: center;'>{home_goals[count]}</h3>", unsafe_allow_html=True)
                            st.markdown(f"<img style='display: block; margin-left: auto; margin-right: auto; width: 75px;' src='{home_logo[count]}'/>", unsafe_allow_html=True)  
                            st.write("")
                            st.write("")

                        # Match date
                        with col3:
                            st.write("")
                            st.markdown("<p style='text-align: center;'><b>Match Date & Time</b></p>", unsafe_allow_html=True)
                            st.markdown(f"<p style='text-align: center;'>{match_date[count]}</p>", unsafe_allow_html=True)
                            st.markdown(f"<p style='text-align: center;'>{home_team[count]} vs. {away_team[count]}</p>", unsafe_allow_html=True)
                    
                        # Away teams
                        with col4:
                            st.markdown(f"<h3 style='text-align: center;'>{away_goals[count]}</h3>", unsafe_allow_html=True)
                            st.markdown(f"<img style='display: block; margin-left: auto; margin-right: auto; width: 75px;' src='{away_logo[count]}'/>", unsafe_allow_html=True)
                            st.write("")
                            st.write("")

                        with col5:
                            st.write("")

                    count += 1

                    st.divider()

            round_count -= 1

        # Social media icons section.
        st.divider()
        st.subheader("Social")

        components.html(
            """
            <script src="https://kit.fontawesome.com/84587c6ecd.js" crossorigin="anonymous"></script>
            <div style="display: flex; flex-direction: row;">
                <a target="_blank" rel="noopener noreferrer" href="https://github.com/digitalghost-dev/"><i class='fa-brands fa-github fa-2x fa-fade' style='color: #000000; padding-right: 1rem'></i></a>
                <a target="_blank" rel="noopener noreferrer" href="https://www.linkedin.com/in/christian-sanchez-nv/"><i class='fa-brands fa-linkedin fa-2x fa-fade' style='color: #000000; padding-right: 1rem'></i></a>
                <a target="_blank" rel="noopener noreferrer" href="https://medium.com/@digitialghost-dev"><i class='fa-brands fa-medium fa-2x fa-fade' style='color: #000000;'></i></a>
            </div>
            """
        )

local_css("style.css")
streamlit_app()