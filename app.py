# app.py
import streamlit as st
from streamlit_javascript import st_javascript
import requests
import os
from datetime import datetime
# Paste this into your Streamlit app (temporary debug)

st.title("GPS Permission Debugger")

st.write("This will check the browser permission state for geolocation, try to request a position, and return a detailed result object. Open DevTools Console to see console logs.")

if st.button("Run GPS debug"):
    js = r"""
    (async function(){
      // Query the Permissions API for geolocation status (if supported)
      let permState = null;
      try {
        if (navigator.permissions && navigator.permissions.query) {
          try {
            const p = await navigator.permissions.query({ name: 'geolocation' });
            permState = p.state; // 'granted', 'prompt', or 'denied'
            console.log('Permissions API state:', permState);
          } catch(e) {
            permState = 'permissions_query_failed';
            console.warn('Permissions API query failed:', e);
          }
        } else {
          permState = 'permissions_api_unsupported';
        }
      } catch(e) {
        permState = 'permissions_api_exception';
      }

      // Helper to standardize error
      function wrapError(e){
        return { ok:false, code: e && e.code ? e.code : null, message: e && e.message ? e.message : String(e) };
      }

      // Now attempt to getCurrentPosition
      if (!navigator.geolocation) {
        return { ok:false, step:'no_geolocation_supported', permission: permState };
      }
      try {
        const res = await new Promise((resolve) => {
          navigator.geolocation.getCurrentPosition(
            pos => resolve({ ok:true, lat: pos.coords.latitude, lon: pos.coords.longitude, acc: pos.coords.accuracy }),
            err => resolve(wrapError(err)),
            { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 }
          );
        });
        // log for devtools
        console.log('Geolocation attempt result:', res);
        return { permission: permState, result: res };
      } catch(e){
        console.error('Unexpected exception while getting position:', e);
        return { permission: permState, result: { ok:false, message: String(e) } };
      }
    })();
    """
    try:
        out = st_javascript(js, key="gps_debug2")
    except Exception as ex:
        st.error(f"st_javascript execution failed: {ex}")
        out = None

    st.write("JS returned:")
    st.json(out)
    st.caption("If JS returned {permission:'denied'} or result shows code/message with 'User denied', open your browser's site settings and allow Location. If permission='prompt' but result shows no popup, try opening the app in a new tab (not embedded) and check console (F12).")
// debug
st.set_page_config(page_title="GPS-only Weather (Polewali fallback)", layout="centered")

# -------- Configuration --------
OPENWEATHER_API_KEY = st.secrets.get("OPENWEATHER_API_KEY") or os.getenv("OPENWEATHER_API_KEY")
DEFAULT_CITY_QUERY = "Polewali,ID"  # Use city name fallback (Polewali, Indonesia). Change if you mean another Polewali.

# -------- Helpers --------
def fetch_weather(lat=None, lon=None, q=None, api_key=None):
    """
    Fetch weather from OpenWeatherMap.
    Provide either (lat, lon) OR q (city name e.g. 'Polewali,ID').
    Returns (ok:bool, payload:dict)
    """
    if api_key is None:
        return False, {"error": "Missing API key"}
    base = "https://api.openweathermap.org/data/2.5/weather"
    params = {"appid": api_key, "units": "metric"}
    if lat is not None and lon is not None:
        params.update({"lat": lat, "lon": lon})
    elif q:
        params.update({"q": q})
    else:
        return False, {"error": "No location provided"}
    try:
        r = requests.get(base, params=params, timeout=8)
        if not r.ok:
            try:
                err = r.json()
            except Exception:
                err = {"text": r.text}
            return False, {"status_code": r.status_code, "error": err}
        return True, r.json()
    except Exception as e:
        return False, {"exception": str(e)}

# -------- UI --------
st.title("GPS-only Weather (default: Polewali)")

st.write(
    "This app requests browser GPS only (no IP lookup). "
    "If you deny or GPS is unavailable, it will use the default location **Polewali**."
)

# Show stored coords if present
if "lat" in st.session_state and "lon" in st.session_state:
    st.success(f"Stored GPS: {st.session_state['lat']:.6f}, {st.session_state['lon']:.6f} (source: browser)")

# Button to request browser GPS (triggers browser permission popup)
if st.button("Get browser location (popup)"):
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
    js_result = None
    try:
        js_result = st_javascript(js, key="get_gps_popup")
    except Exception as e:
        st.warning("streamlit-javascript not available or failed to run. The app will use the default location.")
        js_result = None

    if js_result:
        if js_result.get("ok"):
            st.session_state["lat"] = float(js_result["lat"])
            st.session_state["lon"] = float(js_result["lon"])
            st.success(f"Got GPS — accuracy ~{js_result.get('acc')} m")
        else:
            st.warning(f"Browser location failed or was denied: {js_result.get('error')}")
            # Do NOT call any IP service — explicitly use default city
            if "lat" in st.session_state:
                del st.session_state["lat"]
            if "lon" in st.session_state:
                del st.session_state["lon"]
            st.info(f"Will use default location: {DEFAULT_CITY_QUERY.split(',')[0]}")
    else:
        # No JS result (e.g., package missing or execution failed)
        if "lat" in st.session_state:
            del st.session_state["lat"]
        if "lon" in st.session_state:
            del st.session_state["lon"]
        st.info(f"No GPS obtained; will use default location: {DEFAULT_CITY_QUERY.split(',')[0]}")

st.markdown("---")

# Optionally allow user to explicitly choose default even if GPS present
use_default = st.checkbox(f"Use default location ({DEFAULT_CITY_QUERY.split(',')[0]}) instead of GPS (if GPS available)", value=False)
if use_default and ("lat" in st.session_state or "lon" in st.session_state):
    # clear stored GPS
    if "lat" in st.session_state:
        del st.session_state["lat"]
    if "lon" in st.session_state:
        del st.session_state["lon"]
    st.info("Default location selected; GPS coordinates cleared for this session.")

st.markdown("### Fetch current weather")
if not OPENWEATHER_API_KEY:
    st.error("OpenWeatherMap API key not found. Add OPENWEATHER_API_KEY to Streamlit secrets or environment variables.")
    st.stop()

if st.button("Get current weather"):
    # Prefer GPS if available and user didn't opt to use default
    if "lat" in st.session_state and "lon" in st.session_state and not use_default:
        lat = st.session_state["lat"]
        lon = st.session_state["lon"]
        ok, payload = fetch_weather(lat=lat, lon=lon, api_key=OPENWEATHER_API_KEY)
        source_text = "GPS coordinates"
    else:
        ok, payload = fetch_weather(q=DEFAULT_CITY_QUERY, api_key=OPENWEATHER_API_KEY)
        source_text = f"default: {DEFAULT_CITY_QUERY.split(',')[0]}"

    if not ok:
        st.error(f"Weather API error ({source_text}): {payload}")
    else:
        w = payload
        name = w.get("name") or DEFAULT_CITY_QUERY.split(',')[0]
        main = w.get("main", {})
        temp = main.get("temp")
        feels = main.get("feels_like")
        humidity = main.get("humidity")
        weather_desc = w.get("weather", [{}])[0].get("description", "").title()
        wind = w.get("wind", {}).get("speed")
        st.subheader(f"Current weather in {name}  — (source: {source_text})")
        c1, c2, c3 = st.columns(3)
        c1.metric("Temp (°C)", f"{temp:.1f}" if temp is not None else "N/A", delta=f"Feels {feels:.1f}°C" if feels is not None else "")
        c2.metric("Humidity (%)", f"{humidity}" if humidity is not None else "N/A")
        c3.metric("Wind (m/s)", f"{wind}" if wind is not None else "N/A")
        st.write(f"**Condition:** {weather_desc}")
        st.write("Raw API response:")
        st.json(w)
        st.caption(f"Fetched at {datetime.utcfromtimestamp(w.get('dt', int(datetime.utcnow().timestamp()))).isoformat()} UTC")

st.markdown("---")
st.caption("Privacy: This app only uses browser GPS when you allow it, and otherwise uses the default city 'Polewali'. No IP-based geolocation is used.")
