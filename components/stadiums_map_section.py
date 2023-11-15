import streamlit as st
import plotly.express as px


class StadiumMapSection:
	def __init__(self):
		self.mapbox_access_token = st.secrets["mapbox"]["mapbox_key"]
		px.set_mapbox_access_token(self.mapbox_access_token)

	def create_stadium_map(self, stadiums_df):
		stadium_map = px.scatter_mapbox(
			stadiums_df,
			lat="latitude",
			lon="longitude",
			hover_name="stadium",
			hover_data="team",
		)

		stadium_map.update_layout(
			mapbox_style="light",
			margin={"r": 0, "t": 0, "l": 0, "b": 0},
			mapbox_bounds={"west": -17, "east": 17, "south": 45, "north": 60},
		)

		stadium_map.update_traces(marker=dict(size=8), marker_color="indigo")

		stadium_map.update_mapboxes(zoom=4)

		map_plotly_chart = st.plotly_chart(
			stadium_map, height=1000, use_container_width=True
		)

		return map_plotly_chart

	def display(self, stadiums_df):
		st.subheader("Location of Stadiums")
		map_plotly_chart = self.create_stadium_map(stadiums_df)
		return map_plotly_chart
