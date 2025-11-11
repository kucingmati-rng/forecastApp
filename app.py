# app.py
import streamlit as st
from streamlit_javascript import st_javascript
import requests
import os
from datetime import datetime

# ---------------------------
# Configuration
# ---------------------------
st.set_page_config(page_title="GPS Weather (Polewali fallback)", layout="centered")
st.title("GPS Weather — Allow location for best accuracy")

# Read API key from Streamlit secrets or environment variable
OPENWEATHER_API_KEY = st.secrets.get("OPENWEATHER_API_KEY") or os.getenv("OPENWEATHER_API_KEY")

# Default city fallback if GPS not available / denied
DEFAULT_CITY_QUERY = "Polewali,ID"  # change if you mean another Polewali variant

# ---------------------------
# Helper functions
# ---------------------------
def fetch_weather_by_coords(lat: float, lon: float, api_key: str):
    base = "https://api.openweathermap.org/data/2.5/weather"
    params = {"lat": lat, "lon": lon, "appid": api_key, "units": "metric"}
    r = requests.get(base, params=params, timeout=10)
    return r

def fetch_weather_by_city(q: str, api_key: str):
    base = "https://api.openweathermap.org/data/2.5/weather"
    params = {"q": q, "appid": api_key, "units": "metric"}
    r = requests.get(base, params=params, timeout=10)
    return r

def display_weather_json(resp_json, source_text):
    name = resp_json.get("name") or DEFAULT_CITY_QUERY.split(",")[0]
    main = resp_json.get("main", {})
    temp = main.get("temp")
    feels = main.get("feels_like")
    humidity = main.get("humidity")
    weather_desc = resp_json.get("weather", [{}])[0].get("description", "").title()
    wind = resp_json.get("wind", {}).get("speed")

    st.subheader(f"Current weather in {name}  — (source: {source_text})")
    c1, c2, c3 = st.columns(3)
    c1.metric("Temp (°C)", f"{temp:.1f}" if temp is not None else "N/A",
              delta=f"Feels {feels:.1f}°C" if feels is not None else "")
    c2.metric("Humidity (%)", f"{humidity}" if humidity is not None else "N/A")
    c3.metric("Wind (m/s)", f"{wind}" if wind is not None else "N/A")

    st.write(f"**Condition:** {weather_desc}")
    st.write("Raw API response:")
    st.json(resp_json)
    st.caption(f"Fetched at {datetime.utcfromtimestamp(resp_json.get('dt', int(datetime.utcnow().timestamp()))).isoformat()} UTC")

# ---------------------------
# Main UI
# ---------------------------
st.write("This app will ask you to allow browser location (GPS). If you deny or GPS fails, it will use the default location: **Polewali**.")

# Show stored coords if present
if "lat" in st.session_state and "lon" in st.session_state:
    st.success(f"Stored GPS coordinates: {st.session_state['lat']:.6f}, {st.session_state['lon']:.6f}")

col1, col2 = st.columns([1, 1])
with col1:
    if st.button("Get browser location (popup)"):
        js = r"""
        (async function(){
          function wrapError(e){
            return { ok:false, code: e && e.code ? e.code : null, message: e && e.message ? e.message : String(e) };
          }
          if (!navigator || !navigator.geolocation) {
            return JSON.stringify({ ok:false, step: 'no_geolocation_supported' });
          }
          try {
            const p = await new Promise((resolve) => {
              navigator.geolocation.getCurrentPosition(
                pos => resolve({ ok:true, lat: pos.coords.latitude, lon: pos.coords.longitude, acc: pos.coords.accuracy }),
                err => resolve(wrapError(err)),
                { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 }
              );
            });
            return JSON.stringify(p);
          } catch(e) {
            return JSON.stringify({ ok:false, step:'exception', message: String(e) });
          }
        })();
        """
        js_result = None
        try:
            js_result = st_javascript(js, key="get_gps")
        except Exception as e:
            st.warning("Could not run JS bridge. The app will use default location. (streamlit-javascript error)")
            js_result = None

        # js_result should be a JSON string (if bridge returns properly)
        lat = lon = None
        if isinstance(js_result, str):
            # try parse
            try:
                import json
                parsed = json.loads(js_result)
                if parsed.get("ok"):
                    lat = float(parsed.get("lat"))
                    lon = float(parsed.get("lon"))
                    st.session_state["lat"] = lat
                    st.session_state["lon"] = lon
                    st.success(f"Got GPS: {lat:.6f}, {lon:.6f} (accuracy ~{parsed.get('acc')} m)")
                else:
                    st.warning(f"Geolocation failed or denied: {parsed}")
                    # ensure no coords are stored
                    st.session_state.pop("lat", None)
                    st.session_state.pop("lon", None)
            except Exception as e:
                st.warning(f"Could not parse JS result: {e}. Raw: {js_result}")
                st.session_state.pop("lat", None)
                st.session_state.pop("lon", None)
        else:
            # No valid return — clear coords to use default
            st.info("No JS result from browser. Will use default city when fetching weather.")
            st.session_state.pop("lat", None)
            st.session_state.pop("lon", None)

with col2:
    if st.button("Clear stored location"):
        st.session_state.pop("lat", None)
        st.session_state.pop("lon", None)
        st.info("Stored location cleared; app will use default city until you allow GPS.")

st.markdown("---")

# Manual override / for testing
st.subheader("Manual override (for testing)")
colA, colB = st.columns(2)
mlat = colA.number_input("Manual lat", value=st.session_state.get("lat", 0.0), format="%.6f", key="mlat")
mlon = colB.number_input("Manual lon", value=st.session_state.get("lon", 0.0), format="%.6f", key="mlon")
if st.button("Use manual coordinates"):
    st.session_state["lat"] = float(mlat)
    st.session_state["lon"] = float(mlon)
    st.success(f"Manual coords saved: {mlat:.6f}, {mlon:.6f}")

st.markdown("---")

# Fetch weather
st.subheader("Fetch current weather")
if not OPENWEATHER_API_KEY:
    st.error("OpenWeatherMap API key not found. Add OPENWEATHER_API_KEY in Streamlit secrets or as environment variable.")
    st.stop()

if st.button("Get current weather"):
    # priority: GPS in session_state -> default city
    if "lat" in st.session_state and "lon" in st.session_state:
        lat = st.session_state["lat"]
        lon = st.session_state["lon"]
        try:
            r = fetch_weather_by_coords(lat, lon, OPENWEATHER_API_KEY)
        except Exception as e:
            st.error(f"Error contacting weather API: {e}")
            r = None

        if r is None:
            st.error("No response from weather API.")
        else:
            if not r.ok:
                try:
                    st.error(f"Weather API error (coords): {r.status_code} - {r.json()}")
                except Exception:
                    st.error(f"Weather API error (coords): {r.status_code} - {r.text}")
            else:
                display_weather_json(r.json(), source_text="GPS coordinates")
    else:
        try:
            r = fetch_weather_by_city(DEFAULT_CITY_QUERY, OPENWEATHER_API_KEY)
        except Exception as e:
            st.error(f"Error contacting weather API: {e}")
            r = None

        if r is None:
            st.error("No response from weather API.")
        else:
            if not r.ok:
                try:
                    st.error(f"Weather API error (default city): {r.status_code} - {r.json()}")
                except Exception:
                    st.error(f"Weather API error (default city): {r.status_code} - {r.text}")
            else:
                display_weather_json(r.json(), source_text=f"default city: {DEFAULT_CITY_QUERY.split(',')[0]}")

st.markdown("---")
st.caption("Privacy: This app uses browser GPS only when you allow it. If you deny, it uses the default city Polewali. No IP lookup is performed.")
