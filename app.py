import streamlit as st
from streamlit_javascript import st_javascript
import requests
import os
from datetime import datetime

# -------------------------
# Config / Helpers
# -------------------------
st.set_page_config(page_title="GPS Weather", layout="centered")
OPENWEATHER_API_KEY = st.secrets.get("OPENWEATHER_API_KEY") or os.getenv("OPENWEATHER_API_KEY")

def get_ip_location():
    """Approximate location from IP using ipinfo.io"""
    try:
        r = requests.get("https://ipinfo.io/json", timeout=6)
        r.raise_for_status()
        data = r.json()
        loc = data.get("loc")
        if loc:
            lat, lon = map(float, loc.split(","))
            return {"lat": lat, "lon": lon, "source": "ipinfo"}
    except Exception as e:
        st.debug(f"IP lookup failed: {e}")
    return None

def fetch_weather(lat, lon, api_key):
    """Call OpenWeatherMap current weather and return tuple (ok, data_or_error)"""
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {"lat": lat, "lon": lon, "appid": api_key, "units": "metric"}
    try:
        r = requests.get(url, params=params, timeout=8)
        if not r.ok:
            # try to get json error body
            try:
                err = r.json()
            except Exception:
                err = {"text": r.text}
            return False, {"status_code": r.status_code, "error": err}
        return True, r.json()
    except Exception as e:
        return False, {"exception": str(e)}

# -------------------------
# UI: Location request + fallback
# -------------------------
st.title("GPS Weather — allow location for best accuracy")

st.write(
    "Click **Get location** to allow the browser to share your GPS coordinates (popup). "
    "If you deny or if geolocation isn't available, we'll fall back to approximate IP location."
)

# Show stored coords (if any)
if "lat" in st.session_state and "lon" in st.session_state:
    st.success(f"Stored location: {st.session_state['lat']:.6f}, {st.session_state['lon']:.6f} (source: {st.session_state.get('loc_source','unknown')})")

col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    if st.button("Get location from browser (popup)"):
        # JS to request geolocation; returns object {ok, lat, lon, acc} or {ok:false, error:...}
        js = """
        async function getGeo() {
          return new Promise((resolve) => {
            if (!navigator.geolocation) {
              resolve({ok:false, error: 'Geolocation unsupported'});
              return;
            }
            navigator.geolocation.getCurrentPosition(
              (pos) => {
                resolve({ok:true, lat: pos.coords.latitude, lon: pos.coords.longitude, acc: pos.coords.accuracy});
              },
              (err) => {
                resolve({ok:false, error: err.message});
              },
              {enableHighAccuracy:true, timeout:10000}
            );
          });
        }
        getGeo();
        """
        js_result = st_javascript(js, key="get_loc")
        if js_result:
            if js_result.get("ok"):
                st.session_state["lat"] = float(js_result["lat"])
                st.session_state["lon"] = float(js_result["lon"])
                st.session_state["loc_source"] = "browser_gps"
                st.success(f"Got browser GPS — accuracy ~{js_result.get('acc')} m")
            else:
                st.warning(f"Browser location failed: {js_result.get('error')}")
                # try IP fallback automatically
                ip_loc = get_ip_location()
                if ip_loc:
                    st.session_state["lat"] = ip_loc["lat"]
                    st.session_state["lon"] = ip_loc["lon"]
                    st.session_state["loc_source"] = ip_loc.get("source", "ip")
                    st.info(f"Using IP-based approximate location: {st.session_state['lat']:.6f}, {st.session_state['lon']:.6f}")
                else:
                    st.error("Could not obtain location automatically. Enter coordinates manually below.")
        else:
            st.info("No JS result — falling back to IP lookup.")
            ip_loc = get_ip_location()
            if ip_loc:
                st.session_state["lat"] = ip_loc["lat"]
                st.session_state["lon"] = ip_loc["lon"]
                st.session_state["loc_source"] = ip_loc.get("source", "ip")
                st.info(f"Using IP-based approximate location: {st.session_state['lat']:.6f}, {st.session_state['lon']:.6f}")
            else:
                st.error("IP lookup failed. Enter coordinates manually below.")

st.markdown("---")
st.subheader("Manual override / fallback")
colA, colB = st.columns(2)
with colA:
    manual_lat = st.number_input("Latitude", value=st.session_state.get("lat", 0.0), format="%.6f", key="manual_lat")
with colB:
    manual_lon = st.number_input("Longitude", value=st.session_state.get("lon", 0.0), format="%.6f", key="manual_lon")
if st.button("Use manual coordinates"):
    st.session_state["lat"] = float(manual_lat)
    st.session_state["lon"] = float(manual_lon)
    st.session_state["loc_source"] = "manual"
    st.success("Using manual coordinates.")

# -------------------------
# UI: Fetch weather
# -------------------------
st.markdown("---")
st.subheader("Fetch current weather")
if "lat" not in st.session_state or "lon" not in st.session_state:
    st.info("No coordinates yet. Click 'Get location' or enter them manually.")
else:
    st.write(f"Location being used: **{st.session_state['lat']:.6f}, {st.session_state['lon']:.6f}** (source: {st.session_state.get('loc_source')})")

    if not OPENWEATHER_API_KEY:
        st.error("OpenWeatherMap API key not found. Add `OPENWEATHER_API_KEY` to Streamlit secrets or environment variables.")
        st.stop()

    if st.button("Get weather now"):
        ok, data = fetch_weather(st.session_state["lat"], st.session_state["lon"], OPENWEATHER_API_KEY)
        if not ok:
            st.error(f"Weather API error: {data}")
        else:
            w = data
            name = w.get("name") or "your area"
            main = w.get("main", {})
            temp = main.get("temp")
            feels = main.get("feels_like")
            humidity = main.get("humidity")
            weather_desc = w.get("weather", [{}])[0].get("description", "").title()
            wind = w.get("wind", {}).get("speed")
            st.subheader(f"Current weather in {name}")
            c1, c2, c3 = st.columns(3)
            c1.metric("Temp (°C)", f"{temp:.1f}" if temp is not None else "N/A", delta=f"Feels {feels:.1f}°C" if feels is not None else "")
            c2.metric("Humidity (%)", f"{humidity}" if humidity is not None else "N/A")
            c3.metric("Wind (m/s)", f"{wind}" if wind is not None else "N/A")
            st.write(f"**Condition:** {weather_desc}")
            st.write("Raw API response:")
            st.json(w)
            st.caption(f"Fetched at {datetime.utcfromtimestamp(w.get('dt', int(datetime.utcnow().timestamp()))).isoformat()} UTC")

st.markdown("---")
st.caption("Privacy: location is used only to fetch weather in this session and is not sent to any third party besides the weather API and optional ipinfo service for fallback.")
