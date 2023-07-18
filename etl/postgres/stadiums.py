"""
This file pulls data from an API relating to the English Premier League stadium location data and loads it into BigQuery.
"""

# System libraries
import os

# Importing needed libraries.
from google.cloud import secretmanager
from google.cloud import bigquery
import pandas as pd
import requests

# Settings the project environment.
os.environ["GCLOUD_PROJECT"] = "cloud-data-infrastructure"

# Settings the project environment.
LOCATIONS_TABLE = "cloud-data-infrastructure.premier_league_dataset.stadiums"


def gcp_secret():
    """Fetching RapidAPI key from Secret Manager"""

    client = secretmanager.SecretManagerServiceClient()
    name = "projects/463690670206/secrets/go-api/versions/1"
    response = client.access_secret_version(request={"name": name})
    payload = response.payload.data.decode("UTF-8")

    return payload


def call_api():
    """Calling the API then filling in the empty lists"""

    payload = gcp_secret()

    # Building GET request to retrieve data.
    response = requests.request("GET", payload, timeout=20)
    json_res = response.json()

    # Empty lists that will be filled and then used to create a dataframe.
    team_list = []
    stadium_list = []
    lat_list = []
    lon_list = []
    capacity_list = []
    year_opened = []

    count = 0
    while count < 20:
        # Retrieving team name.
        team_list.append(str(json_res[count]["team"]))

        # Retrieving stadium name.
        stadium_list.append(str(json_res[count]["stadium"]))

        # Retrieving stadium's latitude.
        lat_list.append(float(json_res[count]["latitude"]))

        # Retrieving stadium's longitude.
        lon_list.append(float(json_res[count]["longitude"]))

        # Retrieving stadium's capacity.
        capacity_list.append(str(json_res[count]["capacity"]))

        # Retrieving stadium's year opened.
        year_opened.append(str(json_res[count]["year_opened"]))

        count += 1

    return team_list, stadium_list, lat_list, lon_list, capacity_list, year_opened


def dataframe():
    """This function creates a datafreame from lists created in the last function: call_api()"""

    team_list, stadium_list, lat_list, lon_list, capacity_list, year_opened = call_api()

    # Setting the headers then zipping the lists to create a dataframe.
    headers = ["team", "stadium", "latitude", "longitude", "capacity", "year_opened"]
    zipped = list(
        zip(team_list, stadium_list, lat_list, lon_list, capacity_list, year_opened)
    )

    locations_df = pd.DataFrame(zipped, columns=headers)

    return locations_df


class Locations:
    """Functions to drop and load the locations table."""

    def drop(self):
        """Dropping the BigQuery table"""

        client = bigquery.Client()
        query = f"""
            DROP TABLE 
            {LOCATIONS_TABLE}
        """

        client.query(query)

        print("Location table dropped...")

    def load(self):
        """Loading the dataframe to the BigQuery table"""

        locations_df = (
            dataframe()
        )  # Getting dataframe creating in dataframe() function.

        client = bigquery.Client()

        job = client.load_table_from_dataframe(
            locations_df, LOCATIONS_TABLE
        )  # Make an API request.
        job.result()  # Wait for the job to complete.

        table = client.get_table(LOCATIONS_TABLE)  # Make an API request.

        print(f"Loaded {table.num_rows} rows and {len(table.schema)} columns")


# Creating an instance of the class.
locations = Locations()

if __name__ == "__main__":
    # Calling the functions.
    locations.drop()
    locations.load()