# app.py
# Path: app.py
"""
Streamlit Forecast App — FREE APIs (Open-Meteo + Nominatim + ipapi.co)
Features:
- Browser GPS (best accuracy), IP-based fallback, City search (Nominatim)
- No OpenWeather key required (uses Open-Meteo)
- Shows current + hourly (12h) + 7-day forecast, simple charts
"""

from typing import Optional, Tuple, Dict, Any
from datetime import datetime, timezone
import urllib.parse

import streamlit as st
import streamlit.components.v1 as components
import requests
import pandas as pd
import matplotlib.pyplot as plt

# ---------- CONFIG ----------
st.set_page_config(page_title="Free Forecast App", layout="centered")
DEFAULT_UNITS = "metric"  # Open-Meteo returns Celsius by default

# ---------- UTIL (cache network calls) ----------
@st.cache_data(ttl=300)
def ip_geolocation() -> Optional[dict]:
    try:
        r = requests.get("https://ipapi.co/json/", timeout=6)
        if r.ok:
            return r.json()
    except Exception:
        return None
    return None

@st.cache_data(ttl=86400)
def geocode_city_nominatim(city: str) -> Optional[dict]:
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": city, "format": "json", "limit": 1}
    headers = {"User-Agent": "FreeForecastApp/1.0 (+https://example.com)"}
    try:
        r = requests.get(url, params=params, headers=headers, timeout=8)
        r.raise_for_status()
        data = r.json()
        if data:
            return data[0]
    except Exception:
        return None
    return None

@st.cache_data(ttl=300)
def open_meteo_forecast(lat: float, lon: float, timezone_str: str = "auto") -> Optional[dict]:
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "temperature_2m,relativehumidity_2m,precipitation,weathercode",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,weathercode",
        "forecast_days": 8,  # today + 7 days
        "timezone": timezone_str,
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None

def coords_from_query() -> Optional[Tuple[float, float]]:
    qp = st.experimental_get_query_params()
    if "lat" in qp and "lon" in qp:
        try:
            return float(qp["lat"][0]), float(qp["lon"][0])
        except Exception:
            return None
    return None

def clear_query_params():
    st.experimental_set_query_params()

def js_geolocation_redirect_button(label: str = "Get my location (browser GPS)"):
    html = f"""
    <div>
      <button id="getloc">{label}</button>
      <p id="msg" style="font-size:0.9rem;color:#666;margin-top:8px"></p>
    </div>
    <script>
    const btn = document.getElementById("getloc");
    const msg = document.getElementById("msg");
    btn.onclick = () => {{
      if (!navigator.geolocation) {{
        msg.innerText = "Geolocation not supported by your browser.";
        return;
      }}
      msg.innerText = "Requesting location… (browser may ask for permission)";
      navigator.geolocation.getCurrentPosition(
        (pos) => {{
          const lat = pos.coords.latitude;
          const lon = pos.coords.longitude;
          const newUrl = window.location.pathname + "?lat=" + lat + "&lon=" + lon + "&source=gps";
          window.location.replace(newUrl);
        }},
        (err) => {{
          msg.innerText = "Error obtaining location: " + err.message;
        }},
        {{enableHighAccuracy:true, timeout:10000, maximumAge:60000}}
      );
    }};
    </script>
    """
    components.html(html, height=120)

# ---------- UI: Sidebar ----------
st.title("🌤️ Free Forecast App")
st.sidebar.header("Location & settings")

loc_choice = st.sidebar.radio("Choose location source:", ("Browser GPS (best)", "IP-based (fallback)", "Search city"))
units = st.sidebar.selectbox("Units", ("metric",))  # Open-Meteo returns Celsius — keep simple
if st.sidebar.button("Clear saved location / params"):
    clear_query_params()
    st.experimental_rerun()

# ---------- Determine coordinates ----------
lat_lon = coords_from_query()
lat = lon = None
location_name = None
location_source = None

if loc_choice == "Browser GPS (best)":
    if lat_lon:
        lat, lon = lat_lon
        location_source = "Browser GPS"
    else:
        st.sidebar.write("Click the button to let your browser share location (high accuracy).")
        js_geolocation_redirect_button()
        st.sidebar.write("If permission denied, use IP-based or city search.")
        st.stop()

elif loc_choice == "IP-based (fallback)":
    ipdata = ip_geolocation()
    if not ipdata:
        st.sidebar.error("IP geolocation failed.")
    else:
        # ipapi gives latitude/longitude keys
        lat = float(ipdata.get("latitude") or ipdata.get("lat") or 0)
        lon = float(ipdata.get("longitude") or ipdata.get("lon") or 0)
        location_name = ipdata.get("city") or ipdata.get("region") or ipdata.get("country_name")
        location_source = "IP-based"

elif loc_choice == "Search city":
    city_query = st.sidebar.text_input("City name (e.g. Jakarta, Indonesia)", "")
    if st.sidebar.button("Find"):
        if not city_query.strip():
            st.sidebar.warning("Type a city name first.")
            st.stop()
        geo = geocode_city_nominatim(city_query.strip())
        if not geo:
            st.sidebar.error("City not found (Nominatim). Try a different query.")
            st.stop()
        lat = float(geo["lat"])
        lon = float(geo["lon"])
        display_name = geo.get("display_name", "")
        location_name = display_name
        location_source = "City search"
        # set query params so user can bookmark location
        st.experimental_set_query_params(lat=lat, lon=lon, source="city", city=urllib.parse.quote_plus(city_query.strip()))
        st.experimental_rerun()
    else:
        # allow bookmark / url with lat/lon to populate
        if lat_lon:
            lat, lon = lat_lon
            location_source = "From query"
        else:
            st.sidebar.info("Enter a city and click Find, or use GPS/IP.")
            st.stop()

if lat is None or lon is None:
    qp_coords = coords_from_query()
    if qp_coords:
        lat, lon = qp_coords
        location_source = "Query param"

if lat is None or lon is None:
    st.info("No location provided yet. Choose Browser GPS, IP-based, or Search city.")
    st.stop()

# ---------- Fetch forecast ----------
with st.spinner("Fetching forecast (free) ..."):
    forecast = open_meteo_forecast(lat=lat, lon=lon, timezone_str="auto")

if not forecast:
    st.error("Failed to fetch forecast from Open-Meteo. Check network.")
    st.stop()

# ---------- Parse and display ----------
# Show header
display_loc = location_name or f"Lat {lat:.4f}, Lon {lon:.4f}"
col1, col2 = st.columns([3, 1])
with col1:
    st.subheader(display_loc)
    if location_source:
        st.caption(f"Location source: {location_source}")
with col2:
    if st.button("Set as default (add to URL)"):
        st.experimental_set_query_params(lat=lat, lon=lon, source=location_source or "manual")
        st.experimental_rerun()

# Helper: weather code → text (basic)
WEATHER_CODE_MAP = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Drizzle: Light",
    53: "Drizzle: Moderate",
    55: "Drizzle: Dense",
    61: "Rain: Slight",
    63: "Rain: Moderate",
    65: "Rain: Heavy",
    71: "Snow: Slight",
    73: "Snow: Moderate",
    75: "Snow: Heavy",
    80: "Rain showers: Slight",
    81: "Rain showers: Moderate",
    82: "Rain showers: Violent",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}

def wc_text(code: int) -> str:
    return WEATHER_CODE_MAP.get(int(code), f"Code {code}")

# Current (nearest hour)
try:
    tz = forecast.get("timezone", "UTC")
    hourly = forecast.get("hourly", {})
    hourly_times = hourly.get("time", [])
    temps = hourly.get("temperature_2m", [])
    rh = hourly.get("relativehumidity_2m", [])
    precip = hourly.get("precipitation", [])
    wcodes = hourly.get("weathercode", [])
    # find nearest hour index
    now_local = datetime.now(timezone.utc).astimezone()  # local tz object
    now_iso = now_local.replace(minute=0, second=0, microsecond=0).isoformat()
    # Find index by matching date/time prefix (safe fallback to first)
    idx = 0
    for i, t in enumerate(hourly_times):
        if t.startswith(now_local.strftime("%Y-%m-%dT%H")):
            idx = i
            break
    curr_temp = temps[idx] if idx < len(temps) else None
    curr_rh = rh[idx] if idx < len(rh) else None
    curr_prec = precip[idx] if idx < len(precip) else None
    curr_code = wcodes[idx] if idx < len(wcodes) else None
except Exception:
    curr_temp = curr_rh = curr_prec = curr_code = None

st.markdown("### Now")
if curr_temp is not None:
    st.write(f"**{wc_text(curr_code)}** — {curr_temp}°C")
    st.write(f"Humidity: {curr_rh}% · Precip (hour): {curr_prec} mm")
else:
    st.write("Current conditions unavailable.")

# Hourly mini-plot (next 12 hours)
st.markdown("### Next 12 hours")
try:
    hours_count = min(12, len(hourly_times))
    next_times = hourly_times[:hours_count]
    next_temps = temps[:hours_count]
    df_h = pd.DataFrame({"time": next_times, "temp": next_temps})
    df_h["time_readable"] = pd.to_datetime(df_h["time"]).dt.strftime("%m-%d %H:%M")
    fig, ax = plt.subplots(figsize=(7, 2.4))
    ax.plot(df_h["time_readable"], df_h["temp"], marker="o")
    ax.set_ylabel("°C")
    ax.set_xticklabels(df_h["time_readable"], rotation=45, ha="right")
    ax.set_title("Hourly temperature (next 12h)")
    st.pyplot(fig)
except Exception:
    st.write("Hourly plot unavailable.")

# Daily table + plot (today + 7 days)
st.markdown("### 7-day forecast")
try:
    daily = forecast.get("daily", {})
    d_times = daily.get("time", [])
    d_min = daily.get("temperature_2m_min", [])
    d_max = daily.get("temperature_2m_max", [])
    d_prec = daily.get("precipitation_sum", [])
    d_wcodes = daily.get("weathercode", [])

    rows = []
    for i, dt in enumerate(d_times):
        rows.append({
            "date": dt,
            "min": d_min[i] if i < len(d_min) else None,
            "max": d_max[i] if i < len(d_max) else None,
            "precip_mm": d_prec[i] if i < len(d_prec) else None,
            "desc": wc_text(d_wcodes[i]) if i < len(d_wcodes) else "",
        })
    df_d = pd.DataFrame(rows).set_index("date")
    st.dataframe(df_d)

    fig2, ax2 = plt.subplots(figsize=(7, 3))
    ax2.plot(df_d.index, df_d["min"], marker="o", label="Min")
    ax2.plot(df_d.index, df_d["max"], marker="o", label="Max")
    ax2.set_ylabel("°C")
    ax2.set_xticklabels(df_d.index, rotation=45, ha="right")
    ax2.legend()
    ax2.set_title("Daily min / max")
    st.pyplot(fig2)
except Exception:
    st.write("Daily forecast unavailable.")

# Raw data debug
with st.expander("Raw forecast JSON"):
    st.json(forecast)

st.success("Forecast loaded (Open-Meteo, free) ✅")
st.markdown("---")
st.caption("APIs used: Open-Meteo (forecast), Nominatim (city geocoding), ipapi.co (IP location). No API keys required.")
