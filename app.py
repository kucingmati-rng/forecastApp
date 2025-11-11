
import streamlit as st
import requests
import os
from datetime import datetime

# ---- Helpers ----
OPENWEATHER_API_KEY = st.secrets.get("OPENWEATHER_API_KEY") or os.getenv("OPENWEATHER_API_KEY")

def get_ip_location():
    """Fallback: approximate location from IP using ipinfo.io (free, limited)"""
    try:
        r = requests.get("https://ipinfo.io/json", timeout=5)
        if r.ok:
            data = r.json()
            loc = data.get("loc")  # "lat,lon"
            if loc:
                lat, lon = map(float, loc.split(","))
                return {"lat": lat, "lon": lon, "source": "ipinfo"}
    except Exception as e:
        st.debug(f"ip lookup failed: {e}")
    return None

def get_weather(lat, lon, api_key):
    """Call OpenWeatherMap current weather"""
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {"lat": lat, "lon": lon, "appid": api_key, "units": "metric"}
    r = requests.get(url, params=params, timeout=8)
    r.raise_for_status()
    return r.json()

# ---- Streamlit UI ----
st.set_page_config(page_title="Notebook → Streamlit Weather", layout="centered")
st.title("Weather by GPS (Notebook → Streamlit)")

st.write("This app tries browser GPS first. If denied, it uses an IP-based fallback (less precise).")

# Try browser GPS via streamlit-javascript (graceful fallback if not available)
lat = st.session_state.get("lat")
lon = st.session_state.get("lon")
source = None

try:
    from streamlit_javascript import st_javascript
    js_code = """
    async function getGeo() {
      return new Promise((resolve, reject) => {
        if (!navigator.geolocation) {
          resolve({ok:false, msg: 'no geolocation'});
        }
        navigator.geolocation.getCurrentPosition(
          (pos) => { resolve({ok:true, lat: pos.coords.latitude, lon: pos.coords.longitude}); },
          (err) => { resolve({ok:false, msg: err.message}); },
          {enableHighAccuracy:true, timeout:10000}
        );
      });
    }
    getGeo();
    """
    js_result = st_javascript(js_code, key="geo")
    if js_result and isinstance(js_result, dict) and js_result.get("ok"):
        lat = js_result["lat"]
        lon = js_result["lon"]
        source = "browser_gps"
        st.success("Got GPS from browser.")
    else:
        st.info("Browser GPS not available or denied — will use IP-based fallback.")
except Exception as e:
    st.info("streamlit-javascript not available — will use IP fallback.")
    # (we continue to IP fallback below)

# If no GPS yet, do IP fallback
if lat is None or lon is None:
    loc = get_ip_location()
    if loc:
        lat = loc["lat"]
        lon = loc["lon"]
        source = loc.get("source", "ip")
    else:
        st.error("Could not determine location automatically. Enter coordinates manually.")
        col1, col2 = st.columns(2)
        with col1:
            lat = st.number_input("Latitude", value=0.0, format="%.6f")
        with col2:
            lon = st.number_input("Longitude", value=0.0, format="%.6f")
        source = "manual"

st.write(f"Location: **{lat:.6f}, {lon:.6f}** (source: {source})")

if not OPENWEATHER_API_KEY:
    st.error("OpenWeatherMap API key not found. Put it in Streamlit secrets as OPENWEATHER_API_KEY.")
else:
    try:
        weather = get_weather(lat, lon, OPENWEATHER_API_KEY)
        # parse weather
        name = weather.get("name")
        main = weather.get("main", {})
        temp = main.get("temp")
        feels = main.get("feels_like")
        humidity = main.get("humidity")
        weather_desc = weather.get("weather", [{}])[0].get("description", "").title()
        wind = weather.get("wind", {}).get("speed")

        st.subheader(f"Current weather in {name or 'your area'}")
        cols = st.columns(3)
        cols[0].metric("Temperature (°C)", f"{temp:.1f}" if temp is not None else "N/A", delta=f"Feels {feels:.1f}°C" if feels is not None else "")
        cols[1].metric("Humidity (%)", f"{humidity}" if humidity is not None else "N/A")
        cols[2].metric("Wind (m/s)", f"{wind}" if wind is not None else "N/A")

        st.write(f"**Condition:** {weather_desc}")
        st.write("Full data (raw):")
        st.json(weather)

        # small timestamp
        st.caption(f"Fetched at {datetime.utcfromtimestamp(weather.get('dt', int(datetime.utcnow().timestamp()))).isoformat()} UTC")
    except Exception as e:
        st.error(f"Could not fetch weather: {e}")
