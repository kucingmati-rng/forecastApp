# app.py -- single self-contained diagnostic (streamlit-javascript)
import streamlit as st
import json
from time import sleep

st.set_page_config(page_title="GPS diagnostic", layout="centered")
st.title("GPS diagnostic (streamlit-javascript)")

st.markdown("""
This page runs three tests **in order** to find where the failure is:
1. Basic bridge sanity test (JS -> Python simple string result)  
2. Navigator existence test (detect if browser supports geolocation)  
3. Full geolocation call (returns JSON stringified result)
  
Run tests on the same device/browser where you saw the issue (Android / Windows). After clicking each button, wait a few seconds for results to appear.
""")

try:
    from streamlit_javascript import st_javascript
except Exception as e:
    st.error(f"Import error for streamlit_javascript: {e}")
    st.stop()

# ---- Test 1: basic JS bridge sanity ----
st.subheader("Test 1 — Basic JS bridge sanity")
st.write("This test runs a minimal JS expression that returns a JSON string. Expected: parsed JSON object {'hello':'world'}")
if st.button("Run Test 1 (bridge)"):
    try:
        raw = st_javascript("JSON.stringify({hello:'world'})", key="t1")
    except Exception as ex:
        st.error(f"st_javascript raised exception: {ex}")
        raw = None
    st.write("raw returned value (should be a JSON string):")
    st.write(raw)
    parsed = None
    if raw:
        try:
            parsed = json.loads(raw)
            st.success("Parsed JSON (OK):")
            st.json(parsed)
        except Exception as e:
            st.error(f"Could not parse raw as JSON: {e}")
            st.write("raw (repr):", repr(raw))
    else:
        st.warning("No raw value returned (None/empty/0)")

st.markdown("---")

# ---- Test 2: navigator.geolocation existence ----
st.subheader("Test 2 — navigator.geolocation availability")
st.write("This checks whether the browser environment even exposes navigator.geolocation.")
if st.button("Run Test 2 (navigator)"):
    js = "JSON.stringify({ navigator_geolocation: !!(navigator && navigator.geolocation) })"
    try:
        raw2 = st_javascript(js, key="t2")
    except Exception as ex:
        st.error(f"st_javascript raised exception: {ex}")
        raw2 = None
    st.write("raw returned value:")
    st.write(raw2)
    if raw2:
        try:
            st.json(json.loads(raw2))
        except Exception as e:
            st.error(f"Could not parse: {e}")
            st.write("raw repr:", repr(raw2))

st.markdown("---")

# ---- Test 3: full geolocation (stringified) ----
st.subheader("Test 3 — full geolocation attempt (stringified)")
st.write("This will request permission in the browser. The browser should show the Allow/Block popup. If no popup appears, open the app in a normal tab (not embedded).")
if st.button("Run Test 3 (geolocation)"):
    js = r"""
    (async function(){
      function wrapError(e){
        return {ok:false, code: e && e.code ? e.code : null, message: e && e.message ? e.message : String(e)};
      }
      if (!navigator || !navigator.geolocation) {
        return JSON.stringify({ok:false, step:'no_geolocation_supported'});
      }
      try {
        const p = await new Promise((resolve) => {
          navigator.geolocation.getCurrentPosition(
            pos => resolve({ok:true, lat: pos.coords.latitude, lon: pos.coords.longitude, acc: pos.coords.accuracy}),
            err => resolve(wrapError(err)),
            {enableHighAccuracy:true, timeout:15000, maximumAge:0}
          );
        });
        return JSON.stringify({ok:true, result:p});
      } catch(e){
        return JSON.stringify({ok:false, step:'exception', message:String(e)});
      }
    })();
    """
    try:
        raw3 = st_javascript(js, key="t3")
    except Exception as ex:
        st.error(f"st_javascript raised exception: {ex}")
        raw3 = None

    st.write("raw returned value (string):")
    st.write(raw3)
    if raw3:
        try:
            st.write("parsed JSON:")
            st.json(json.loads(raw3))
        except Exception as e:
            st.error(f"Could not parse returned string as JSON: {e}")
            st.write("raw repr:", repr(raw3))
