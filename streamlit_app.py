import os
import tarfile
import pydeck as pdk
import streamlit as st

# --- 1. Setup: Extract Tiles ---
TILE_DIR = "static/tiles"
TILE_ARCHIVE = "tiles_archive.tar.gz"

# Extraction logic: Only runs if the directory is missing or empty
if not os.path.exists("static/tiles/metadata.json"):
    if os.path.exists(TILE_ARCHIVE):
        with st.spinner("Extracting map tiles..."):
            with tarfile.open(TILE_ARCHIVE, "r:gz") as tar:
                tar.extractall(path=".")
            st.success("Extraction complete!")
    else:
        st.error(f"Archive {TILE_ARCHIVE} not found.")

# --- 2. Streamlit Config ---
os.makedirs(".streamlit", exist_ok=True)
with open(".streamlit/config.toml", "w") as f:
    f.write("[server]\nenableStaticServing = true\n")

st.set_page_config(page_title="OAC Odds Ratio Map", layout="wide")
st.title("Gambling Local Area Risk Assessment")

# --- DEBUG INFO ---
if os.path.exists(TILE_DIR):
    file_count = sum([len(files) for r, d, files in os.walk(TILE_DIR)])
    st.sidebar.info(f"Tiles found: {file_count}")

tab1, tab2, tab3 = st.tabs(["Interactive Map", "How to Use", "Acknowledgments"])

with tab1:
    ui_col1, ui_col2, ui_col3 = st.columns([2, 2, 3])
    with ui_col1:
        analysis_choice = st.radio("Style:", ["Combined Effect", "Tobacco", "Alcohol"], horizontal=True)
    with ui_col2:
        granularity_choice = st.segmented_control("Granularity:", ["Subgroup", "Group"], default="Subgroup")
    with ui_col3:
        percentile_tier = st.slider("Risk Threshold:", 1, 10, 10)

    # Path logic
    property_key = "comb_OR" if analysis_choice == "Combined Effect" else ("tob_OR" if analysis_choice == "Tobacco" else "alc_OR")
    if granularity_choice == "Group":
        property_key = "comb_OR_group" if property_key == "comb_OR" else (f"{property_key}_group")
    
    scale_key = "sub_95th" if granularity_choice == "Subgroup" else "grp_95th"
    risk_cutoff_expr = 0.0 if percentile_tier == 10 else 1.0 + (10 - percentile_tier) * 0.08
    
    # REQUIRED: Use /app/static/ for Streamlit Cloud static serving
    tile_url = "/app/static/tiles/{z}/{x}/{y}.pbf"

    gradient_fill_expression = f"""
        properties.{property_key} < {risk_cutoff_expr} ? [148, 163, 184, 25] : (
            properties.{property_key} <= 1.0 ? [34, 197, 94, 160] : (
                properties.{property_key} <= (1.0 + (properties.{scale_key} - 1.0) * 0.33) ? [234, 179, 8, 160] : (
                    properties.{property_key} <= (1.0 + (properties.{scale_key} - 1.0) * 0.66) ? [249, 115, 22, 170] : [220, 38, 38, 190]
                )
            )
        )
    """

    mvt_layer = pdk.Layer(
        "MVTLayer",
        data=tile_url,
        get_fill_color=gradient_fill_expression,
        get_line_color=[100, 116, 139, 30],
        line_width_min_pixels=0.15,
        pickable=True,
        auto_highlight=True,
    )

    st.pydeck_chart(pdk.Deck(
        layers=[mvt_layer],
        initial_view_state=pdk.ViewState(longitude=-3.4360, latitude=55.3781, zoom=5.5),
        map_style="light"
    ))
