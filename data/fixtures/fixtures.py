"""
This file calls the Football API to extract match fixture data
and load the collection and documents into Firestore.
"""

import os
import requests

# Google Cloud library imports.
import firebase_admin
from firebase_admin import firestore
from google.cloud import secretmanager

os.environ["GCLOUD_PROJECT"] = "cloud-data-infrastructure"


# Calling the Football API.
def call_api(secret_name):
    client = secretmanager.SecretManagerServiceClient()
    response = client.access_secret_version(request={"name": secret_name})
    payload = response.payload.data.decode("UTF-8")

    # Headers used for RapidAPI.
    headers = {
        "content-type": "application/octet-stream",
        "X-RapidAPI-Key": payload,
        "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com",
    }

    return headers


class Fixture:
    """Building JSON structure for documents."""

    def __init__(self, date, teams, goals=None):
        self.date = date
        self.teams = teams
        self.goals = goals

    def __repr__(self):
        return f"Fixture(\
                name={self.date}, \
                country={self.teams}, \
                goals={self.goals}\
            )"

    def to_dict(self):
        return {"date": self.date, "teams": self.teams, "goals": self.goals}


# Calls the Football API to retrieve the current round of the regular season.
def get_current_round():
    # Calling variables from previous functions.
    headers = call_api("projects/463690670206/secrets/rapid-api/versions/1")

    url = "https://api-football-v1.p.rapidapi.com/v3/fixtures/rounds"
    querystring = {"league": "39", "season": "2022", "current": "true"}
    response = requests.get(url, headers=headers, params=querystring, timeout=20)

    current_round_response = response.json()["response"][0]
    # example response: "Regular Season - 12"

    return current_round_response


# Retrieving the data for the current round based on get_current_round() function's response.
def retrieve_data_for_current_round():
    # Calling variables from previous functions.
    headers = call_api("projects/463690670206/secrets/rapid-api/versions/1")
    current_round_response = get_current_round()

    url = "https://api-football-v1.p.rapidapi.com/v3/fixtures"
    querystring = {"league": "39", "season": "2022", "round": current_round_response}
    build_current_response = requests.get(
        url, headers=headers, params=querystring, timeout=20
    )

    return build_current_response


def load_firestore():
    current_round_response = get_current_round()
    build_current_response = retrieve_data_for_current_round()

    # Check to see if firebase app has been initialized.
    if not firebase_admin._apps:
        firebase_admin.initialize_app()
    db = firestore.client()

    count = 0
    while count < 10:
        # Dictionaries to be written to each document.
        fixture_date = build_current_response.json()["response"][count]["fixture"][
            "date"
        ]
        teams_dict = build_current_response.json()["response"][count]["teams"]
        goal_dict = build_current_response.json()["response"][count]["goals"]

        # Calling the away and home team names to build document name.
        away_team = build_current_response.json()["response"][count]["teams"]["away"][
            "name"
        ]
        home_team = build_current_response.json()["response"][count]["teams"]["home"][
            "name"
        ]

        fixture = Fixture(date=(fixture_date), teams=teams_dict, goals=goal_dict)
        db.collection(f"{current_round_response}").document(
            f"{away_team} vs {home_team}"
        ).set(fixture.to_dict())

        count += 1

    print(f"Document {current_round_response} has been loaded!")


if __name__ == "__main__":
    load_firestore()
