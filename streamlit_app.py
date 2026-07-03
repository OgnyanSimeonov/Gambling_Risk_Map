import os
import tarfile
import pydeck as pdk
import streamlit as st

# --- 1. Extraction Logic ---
TILE_DIR = "static/tiles"
TILE_ARCHIVE = "tiles_archive.tar.gz"

if not os.path.exists("static/tiles/metadata.json"):
    if os.path.exists(TILE_ARCHIVE):
        with st.spinner("Extracting tiles..."):
            with tarfile.open(TILE_ARCHIVE, "r:gz") as tar:
                tar.extractall(path=".")
    else:
        st.error("Archive not found!")

# --- 2. Helper to serve PBF files correctly ---
# This bypasses the static server issue by reading the file manually
def get_tile(z, x, y):
    path = f"static/tiles/{z}/{x}/{y}.pbf"
    if os.path.exists(path):
        with open(path, "rb") as f:
            return f.read()
    return None

# --- 3. UI and Map ---
st.set_page_config(page_title="OAC Odds Ratio Map", layout="wide")
st.title("Gambling Local Area Risk Assessment")

# We use the relative URL. Pydeck expects a URL that the browser can fetch.
# Because Streamlit's static serving is acting up, we rely on the browser's 
# native ability to fetch from the /static/ path.
tile_url = "./static/tiles/{z}/{x}/{y}.pbf"

mvt_layer = pdk.Layer(
    "MVTLayer",
    data=tile_url,
    get_fill_color=[200, 30, 0, 160],
    pickable=True,
    auto_highlight=True,
    binary=True  # Ensure Pydeck treats this as binary data
)

st.pydeck_chart(pdk.Deck(
    layers=[mvt_layer],
    initial_view_state=pdk.ViewState(longitude=-3.4360, latitude=55.3781, zoom=5.5),
    map_style="light"
))
