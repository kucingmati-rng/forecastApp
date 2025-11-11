# app.py
# Path: app.py
"""
Streamlit Forecast App
Features:
- Browser GPS (via embedded JS + redirect to set query params)
- IP-based geolocation fallback (ipapi.co)
- City search (OpenWeather geocoding)
- Fetches weather from OpenWeather One Call API (uses st.secrets["OPENWEATHER_API_KEY"])
"""

import streamlit as st
import streamlit.components.v1 as components
import requests
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from typing import Optional, Tuple

# ------------------------
# Minimal configuration
# ------------------------
st.set_page_config(page_title="Forecast App", layout="centered")
OPENWEATHER_KEY = st.secrets.get("OPENWEATHER_API_KEY")
if not OPENWEATHER_KEY:
    st.error("OpenWeather API key not found in st.secrets['OPENWEATHER_API_KEY']. Add it and reload.")
    st.stop()

# ------------------------
# Utility functions
# ------------------------
@st.cache_data(ttl=300)
def ip_geolocation() -> Optional[dict]:
    """Get approximate location from IP (fallback)."""
    try:
        r = requests.get("https://ipapi.co/json/", timeout=6)
        if r.ok:
            return r.json()
    except Exception:
        return None
    return None

@st.cache_data(ttl=300)
def geocode_city(city: str) -> Optional[dict]:
    """Use OpenWeather Geocoding API to convert city to lat/lon. Returns first match."""
    try:
        url = "http://api.openweathermap.org/geo/1.0/direct"
        params = {"q": city, "limit": 1, "appid": OPENWEATHER_KEY}
        r = requests.get(url, params=params, timeout=8)
        r.raise_for_status()
        data = r.json()
        if data:
            return data[0]  # dict with name, lat, lon, country, etc.
    except Exception:
        return None
    return None

@st.cache_data(ttl=300)
def fetch_weather(lat: float, lon: float, units: str = "metric") -> Optional[dict]:
    """Fetch current + hourly + daily weather from OpenWeather One Call API."""
    try:
        url = "https://api.openweathermap.org/data/2.5/onecall"
        params = {
            "lat": lat,
            "lon": lon,
            "units": units,
            "exclude": "minutely,alerts",
            "appid": OPENWEATHER_KEY,
        }
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None

def coords_from_query() -> Optional[Tuple[float, float]]:
    """Return lat/lon if present in query params."""
    qp = st.experimental_get_query_params()
    if "lat" in qp and "lon" in qp:
        try:
            lat = float(qp["lat"][0])
            lon = float(qp["lon"][0])
            return lat, lon
        except Exception:
            return None
    return None

def clear_location_query():
    st.experimental_set_query_params()  # clear all query params

def js_geolocation_redirect_button(button_label="Get my location (browser GPS)"):
    """Embed JS to get browser geolocation and redirect with lat/lon query params."""
    html = f"""
    <div>
      <button id="getloc">{button_label}</button>
      <p id="msg"></p>
    </div>
    <script>
    const btn = document.getElementById("getloc");
    const msg = document.getElementById("msg");
    btn.onclick = () => {{
      if (!navigator.geolocation) {{
        msg.innerText = "Geolocation not supported.";
        return;
      }}
      msg.innerText = "Requesting location...";
      navigator.geolocation.getCurrentPosition(
        (pos) => {{
          const lat = pos.coords.latitude;
          const lon = pos.coords.longitude;
          // Redirect back to the Streamlit app with coordinates in query params
          const search = window.location.search;
          const base = window.location.pathname + window.location.hash;
          const newUrl = base + "?lat=" + lat + "&lon=" + lon + "&source=gps";
          // Use replace to avoid creating history entries for privacy
          window.location.replace(newUrl);
        }},
        (err) => {{
          msg.innerText = "Error obtaining location: " + err.message;
        }},
        {{ enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 }}
      );
    }};
    </script>
    """
    components.html(html, height=120)

# ------------------------
# UI - Sidebar
# ------------------------
st.title("📡 Forecast App")

st.sidebar.header("Location selection")
loc_method = st.sidebar.radio("Choose location source:", ("Browser GPS (best)", "IP-based (fallback)", "Search city"))

units = st.sidebar.selectbox("Units", ("metric", "imperial"))
refresh = st.sidebar.button("Clear location & refresh")

if refresh:
    clear_location_query()
    st.experimental_rerun()

# Determine lat/lon and display name
lat_lon = coords_from_query()
location_name = None
location_source = None

if loc_method == "Browser GPS (best)":
    # If lat/lon already in query params, use that, else show button to obtain
    if lat_lon:
        lat, lon = lat_lon
        location_source = "GPS (browser)"
    else:
        st.sidebar.markdown("Use your browser's geolocation API for best accuracy.")
        js_geolocation_redirect_button()
        st.sidebar.write("Or switch to IP-based or Search city if browser permission denied.")
        lat = lon = None

elif loc_method == "IP-based (fallback)":
    ip_data = ip_geolocation()
    if ip_data and "latitude" in ip_data and "longitude" in ip_data:
        lat = float(ip_data["latitude"])
        lon = float(ip_data["longitude"])
    elif ip_data and "lat" in ip_data and "lon" in ip_data:
        lat = float(ip_data["lat"])
        lon = float(ip_data["lon"])
    else:
        # Many IP APIs return lat/lon as floats in keys "latitude"/"longitude" or "lat"/"lon"
        lat = lon = None
    if ip_data:
        city = ip_data.get("city") or ip_data.get("region") or ip_data.get("country_name")
        location_name = city
    location_source = "IP-based"

elif loc_method == "Search city":
    city_query = st.sidebar.text_input("City name (e.g. Jakarta,ID or Bandung)", "")
    if st.sidebar.button("Find city"):
        if city_query.strip():
            ge = geocode_city(city_query.strip())
            if ge:
                lat = ge["lat"]
                lon = ge["lon"]
                location_name = f"{ge.get('name','')}, {ge.get('country','')}"
                # set query params so GPS button / urls reflect coords and user can bookmark
                st.experimental_set_query_params(lat=lat, lon=lon, source="city", city=ge.get("name",""))
                st.experimental_rerun()
            else:
                st.sidebar.error("City not found via OpenWeather geocoding.")
                lat = lon = None
        else:
            st.sidebar.warning("Enter a city name first.")
            lat = lon = None
    else:
        # If user arrived via query params (e.g., redirected from GPS) respect that
        if lat_lon:
            lat, lon = lat_lon
            location_source = "From query"
        else:
            lat = lon = None

# If lat/lon still None but query params present earlier, handle them
if not (lat is not None and lon is not None):
    qp_coords = coords_from_query()
    if qp_coords:
        lat, lon = qp_coords
        location_source = "Query param"

# If we have lat/lon, optionally reverse lookup city name using OpenWeather reverse geocoding
if lat is not None and lon is not None:
    # Try reverse geocoding to get a readable city name (best-effort)
    try:
        rg_url = "http://api.openweathermap.org/geo/1.0/reverse"
        rg_params = {"lat": lat, "lon": lon, "limit": 1, "appid": OPENWEATHER_KEY}
        rg = requests.get(rg_url, params=rg_params, timeout=6)
        if rg.ok:
            rgj = rg.json()
            if isinstance(rgj, list) and rgj:
                loc = rgj[0]
                name_part = loc.get("name") or ""
                country = loc.get("country") or ""
                if name_part:
                    location_name = f"{name_part}, {country}" if country else name_part
    except Exception:
        pass

# ------------------------
# Main content: fetch & show weather
# ------------------------
if lat is None or lon is None:
    st.info("No coordinates available yet. Choose a method and provide location.")
    st.stop()

with st.spinner("Fetching weather..."):
    weather = fetch_weather(lat=lat, lon=lon, units=units)
if not weather:
    st.error("Failed to fetch weather from OpenWeather. Check API key and network.")
    st.stop()

# Header with location & source
col1, col2 = st.columns([3, 1])
with col1:
    st.subheader(location_name or f"Lat {lat:.4f}, Lon {lon:.4f}")
    if location_source:
        st.caption(f"Location source: {location_source}")
with col2:
    if st.button("Use this location as default (set query params)"):
        st.experimental_set_query_params(lat=lat, lon=lon, source=location_source or "user")
        st.experimental_rerun()

# Current weather
current = weather.get("current", {})
curr_dt = datetime.utcfromtimestamp(current.get("dt", 0)).strftime("%Y-%m-%d %H:%M UTC")
temp = current.get("temp")
feels = current.get("feels_like")
desc = current.get("weather", [{}])[0].get("description", "").title()
humidity = current.get("humidity")
wind = current.get("wind_speed")
pressure = current.get("pressure")

st.markdown("### Now")
st.write(f"**{desc}** — {temp}°{'C' if units=='metric' else 'F'} (feels like {feels}°)")
st.write(f"Humidity: {humidity}% · Wind: {wind} {'m/s' if units=='metric' else 'mph'} · Pressure: {pressure} hPa")
st.write(f"Observed: {curr_dt}")

# Hourly (compact)
hourly = weather.get("hourly", [])[:12]  # next 12 hours
if hourly:
    hours = []
    temps = []
    for h in hourly:
        hours.append(datetime.utcfromtimestamp(h["dt"]).strftime("%H:%M"))
        temps.append(h["temp"])
    fig, ax = plt.subplots(figsize=(6, 2.5))
    ax.plot(hours, temps, marker="o")
    ax.set_title("Next 12 hours temperature")
    ax.set_xlabel("")
    ax.set_ylabel(f"Temp ({'°C' if units=='metric' else '°F'})")
    ax.tick_params(axis='x', rotation=45)
    st.pyplot(fig)

# Daily forecast table & plot
daily = weather.get("daily", [])[:8]  # today + 7 days
if daily:
    rows = []
    for d in daily:
        dt = datetime.utcfromtimestamp(d["dt"]).strftime("%a %Y-%m-%d")
        temp_min = d["temp"]["min"]
        temp_max = d["temp"]["max"]
        weather_desc = d.get("weather", [{}])[0].get("description","").title()
        pop = int(d.get("pop", 0) * 100)  # probability of precipitation
        rows.append({"date": dt, "min": temp_min, "max": temp_max, "desc": weather_desc, "pop%": pop})
    df = pd.DataFrame(rows)
    st.markdown("### 7-day forecast")
    st.dataframe(df.set_index("date"))

    # plot daily min/max
    fig2, ax2 = plt.subplots(figsize=(7, 3))
    ax2.plot(df.index, df["min"], marker="o", label="Min")
    ax2.plot(df.index, df["max"], marker="o", label="Max")
    ax2.set_title("7-day min / max temps")
    ax2.set_ylabel(f"Temp ({'°C' if units=='metric' else '°F'})")
    ax2.tick_params(axis='x', rotation=45)
    ax2.legend()
    st.pyplot(fig2)

# Optional: small metadata and raw data toggle
with st.expander("Raw API response (debug)"):
    st.json(weather)

st.success("Weather data loaded ✅")

# Footer: tips
st.markdown("---")
st.caption("Tips: If browser GPS doesn't return location, ensure your browser allows location access. IP geolocation is approximate (city-level). City search uses OpenWeather geocoding.")

