import os
import tarfile
import pydeck as pdk
import streamlit as st

# --- 1. Setup: Extract Tiles on Startup ---
# This ensures the tiles are available at the path the MVTLayer expects
TILE_ARCHIVE = "tiles_archive.tar.gz"
TILE_DIR = "static/tiles"

if not os.path.exists(TILE_DIR):
    if os.path.exists(TILE_ARCHIVE):
        with st.spinner("Initializing map data... this only happens once."):
            os.makedirs("static", exist_ok=True)
            with tarfile.open(TILE_ARCHIVE, "r:gz") as tar:
                tar.extractall(path="static")
    else:
        st.error(f"Error: {TILE_ARCHIVE} not found in the project root.")

# --- 2. Streamlit Config ---
os.makedirs(".streamlit", exist_ok=True)
with open(".streamlit/config.toml", "w") as f:
    f.write("[server]\nenableStaticServing = true\n")

st.set_page_config(
    page_title="OAC Odds Ratio Map | Research Supplement", layout="wide"
)

st.title("Gambling Local Area Risk Assessment: Vector Tile Accelerated Map")
st.write("---")

tab1, tab2, tab3 = st.tabs(
    ["Interactive Map", "How to Use", "Acknowledgments & Data"]
)

with tab1:
    st.markdown(
        """
        This map details the odds ratios of co-occurring gambling behavior across the UK.
        Use the controls below to toggle layers, change granularity, or filter by vulnerability risk.
        """
    )

    ui_col1, ui_col2, ui_col3 = st.columns([2, 2, 3])
    
    with ui_col1:
        analysis_choice = st.radio(
            "Select Risk Profile map view layer style:", 
            options=["Combined Effect", "Tobacco", "Alcohol"], 
            horizontal=True,
            help="• Combined Effect: Average risk calculation.\n• Tobacco: Isolated Tobacco smoking odds ratio risks.\n• Alcohol: Isolated hazardous Alcohol consumption odds ratio risks."
        )
        
    with ui_col2:
        granularity_choice = st.segmented_control(
            "Select OAC Classification Granularity Level:",
            options=["Subgroup", "Group"],
            default="Subgroup",
            help="• Subgroup: Deepest classification granularity.\n• Group: Broader classification level."
        )
        
    with ui_col3:
        percentile_tier = st.slider(
            "Filter Co-occurring Risk Threshold:",
            min_value=1,
            max_value=10,
            value=10,
            step=1,
            help="Slide down to isolate the highest vulnerability clusters."
        )
        if percentile_tier == 10:
            st.caption("✨ **Currently showing: All Areas**")
        else:
            st.caption(f"🎯 **Currently showing: Top {percentile_tier}0% Highest Risk Areas Only**")

    # Resolve property keys
    property_key = "comb_OR"
    scale_key = "sub_95th"
    
    if analysis_choice == "Tobacco":
        property_key = "tob_OR"
    elif analysis_choice == "Alcohol":
        property_key = "alc_OR"
        
    if granularity_choice == "Group":
        scale_key = "grp_95th"
        property_key = f"{property_key}_group" if property_key != "comb_OR" else "comb_OR_group"

    risk_cutoff_expr = 0.0 if percentile_tier == 10 else 1.0 + (10 - percentile_tier) * 0.08

    # Path for static serving in Streamlit
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
        shaded=False,
        stroked=True,
        filled=True,
        get_fill_color=gradient_fill_expression,
        get_line_color=[100, 116, 139, 30],
        line_width_min_pixels=0.15,
        pickable=True,
        auto_highlight=True,
        min_zoom=0,
        max_zoom=11, 
    )

    deck = pdk.Deck(
        layers=[mvt_layer],
        initial_view_state=pdk.ViewState(longitude=-3.4360, latitude=55.3781, zoom=5.5, pitch=0),
        tooltip={"html": "<b>OA Code:</b> {geo_code}<br/><b>Risk Score:</b> {comb_OR}", "style": {"backgroundColor": "#1e293b", "color": "white"}},
        map_style="light",
    )

    st.pydeck_chart(deck, height=750)

with tab2:
    st.header("How to Use This Dashboard")
    st.write("Navigate the map to explore local area vulnerability risk levels.")

with tab3:
    st.header("Acknowledgments & Data Availability")
    st.write("Supported by the EPSRC Centre for Doctoral Training in Mathematical Modelling, Analysis and Computation (MAC-MIGS).")

st.write("---")
st.markdown("<small>Citation: Simeonov et al., Harm Reduction Journal (2026).</small>", unsafe_allow_html=True)
