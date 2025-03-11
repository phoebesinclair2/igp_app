import streamlit as st
import pandas as pd
import requests_cache
from datetime import date
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
import openmeteo_requests
from retry_requests import retry

# reminder of bash command to run app: streamlit run app.py

# Setup Open-Meteo API client with cache and retry on error
cache_session = requests_cache.CachedSession('.cache', expire_after=3600)
retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
openmeteo = openmeteo_requests.Client(session=retry_session)

# Function to get coordinates from postcode
def get_coordinates(postcode):
    geolocator = Nominatim(user_agent="streamlit-geocoder")
    try:
        location = geolocator.geocode(postcode)
        if location:
            return location.latitude, location.longitude
        else:
            return None, None
    except GeocoderTimedOut:
        return None, None

# Function to fetch weather data from Open-Meteo API
def fetch_weather_data(latitude, longitude):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": "temperature_2m,cloud_cover,precipitation",
        "timezone": "auto"
    }

    responses = openmeteo.weather_api(url, params=params)
    response = responses[0]

    # Process hourly weather data
    hourly = response.Hourly()
    hourly_temperature = hourly.Variables(0).ValuesAsNumpy()
    hourly_cloud_cover = hourly.Variables(1).ValuesAsNumpy()
    hourly_precipitation = hourly.Variables(2).ValuesAsNumpy()

    hourly_data = {
        "date": pd.date_range(
            start=pd.to_datetime(hourly.Time(), unit="s", utc=True),
            end=pd.to_datetime(hourly.TimeEnd(), unit="s", utc=True),
            freq=pd.Timedelta(seconds=hourly.Interval()),
            inclusive="left"
        ),
        "temperature_2m": hourly_temperature,
        "cloud_cover": hourly_cloud_cover,
        "precipitation": hourly_precipitation
    }

    return pd.DataFrame(data=hourly_data)

# Initialize session state variables
if "submitted" not in st.session_state:
    st.session_state.submitted = False
if "weather_data" not in st.session_state:
    st.session_state.weather_data = None

# Streamlit App UI
st.title("Trial Data Entry Form")

# Trial Name Input
trial_name = st.text_input("Enter the Trial Name", placeholder="e.g. Greenhouse Test A")

# Trial Start & End Dates
trial_start_date = st.date_input("📅 Select Trial Start Date", min_value=date(2000, 1, 1))
trial_end_date = st.date_input("📅 Select Trial End Date", min_value=trial_start_date)

# Postcode Input
postcode = st.text_input("Enter the Postcode", placeholder="e.g. BS1 1AA (UK)")

# Add Weather Data Option
add_weather = st.radio("Would you like to add weather data from open meteo?", ["No", "Yes"])

# Submit Button
if st.button("Submit Trial Info"):
    # Validate required fields
    if not trial_name:
        st.error("❌ Please enter a **Trial Name**.")
    elif not trial_start_date:
        st.error("❌ Please select a **Trial Start Date**.")
    elif not trial_end_date:
        st.error("❌ Please select a **Trial End Date**.")
    elif not postcode:
        st.error("❌ Please enter a **Location (Postcode)**.")
    else:
        # If all fields are filled, proceed with submission
        st.session_state.submitted = True

        # Get location from postcode
        lat, lon = get_coordinates(postcode)
        if lat is not None and lon is not None:
            st.session_state.lat, st.session_state.lon = lat, lon

            # Fetch weather data if selected
            if add_weather == "Yes":
                with st.spinner("Fetching weather data..."):
                    st.session_state.weather_data = fetch_weather_data(lat, lon)

# Display trial summary if submitted
if st.session_state.submitted:
    st.success(f"✅ Trial '{trial_name}' recorded successfully!")
    st.write(f"**Start Date:** {trial_start_date}")
    st.write(f"**End Date:** {trial_end_date}")
    st.write(f"**Location Coordinates:** {st.session_state.lat}, {st.session_state.lon}")
    st.map({"lat": [st.session_state.lat], "lon": [st.session_state.lon]})

    if add_weather == "Yes" and st.session_state.weather_data is not None:
        st.write("**Weather Data Sample (hourly):**")
        st.dataframe(st.session_state.weather_data.head())  # Show first few rows

        # Allow user to download the data
        csv = st.session_state.weather_data.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Download Full Weather Data", data=csv, file_name="weather_data.csv", mime="text/csv")

    # Button to edit trial information
    if st.button("🔄 Reset form"):
        st.session_state.submitted = False  # Reset the form to allow editing
