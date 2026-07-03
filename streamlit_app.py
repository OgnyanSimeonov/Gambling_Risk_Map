import os
import tarfile
import pydeck as pdk
import streamlit as st
import streamlit.components.v1 as components

# --- 1. Extraction Logic ---
TILE_DIR = "static/tiles"
TILE_ARCHIVE = "tiles_archive.tar.gz"

if not os.path.exists("static/tiles/metadata.json"):
    if os.path.exists(TILE_ARCHIVE):
        with tarfile.open(TILE_ARCHIVE, "r:gz") as tar:
            tar.extractall(path=".")
    else:
        st.error("Archive not found!")

# --- 2. The Map ---
# We point to a URL that we will attempt to proxy through Streamlit
# Note: For MVTLayer in Pydeck, the URL MUST be reachable.
# If the static path still fails, it's a browser CORS security block.
tile_url = "./static/tiles/{z}/{x}/{y}.pbf"

st.title("Gambling Local Area Risk Assessment")

st.pydeck_chart(pdk.Deck(
    layers=[
        pdk.Layer(
            "MVTLayer",
            data=tile_url,
            get_fill_color=[200, 30, 0, 160],
            pickable=True,
            auto_highlight=True,
        )
    ],
    initial_view_state=pdk.ViewState(longitude=-3.4360, latitude=55.3781, zoom=5.5),
    map_style="light"
))

# --- 3. Final Diagnostic ---
st.write("If the map is blank, check the browser console (Right-Click -> Inspect -> Console).")
st.write("If you see 'CORS error' or '404', Streamlit is blocking the static file access.")
