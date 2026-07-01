import json
import os
import geopandas as gpd
import matplotlib.cm as cm
import numpy as np
import pandas as pd
import pydeck as pdk
import shapely
import streamlit as st

# Import the OAC code mappings from your side file
from oac_mappings import oac_group_names, oac_subgroup_names

# --- 1. Page Configuration & Layout ---
st.set_page_config(
    page_title="OAC Odds Ratio Map | Research Supplement", layout="wide"
)

st.title("Gambling Local Area Risk Assessment: Co-Occurring Behaviors Map")
st.write("---")

# --- 2. Data Processing & Caching Core Functions ---
RENAME_MAP = {
    "geo_code": "Output Area Code",
    "SUB_REGION": "Sub-Region",
    "REGION": "Region",
    "POPULATION": "Population",
}


def get_region_list():
    """Dynamically reads the available regions based on your split files."""
    if os.path.exists("regional_data"):
        files = os.listdir("regional_data")
        regions = [f.replace(".parquet", "").replace("_", " ") for f in files if f.endswith(".parquet")]
        return sorted(regions)
    else:
        # Fallback list if the directory isn't read correctly
        return [
            "East Midlands",
            "East of England",
            "London",
            "North East",
            "North West",
            "Scotland",
            "South East",
            "South West",
            "Wales",
            "West Midlands",
            "Yorkshire and The Humber",
        ]


@st.cache_data(persist="disk")
def load_regional_spatial_data(region_name: str):
    """Loads ONLY the requested region's geometry from disk to keep RAM minimal."""
    safe_name = region_name.replace(" ", "_").replace("/", "_")
    file_path = f"regional_data/{safe_name}.parquet"
    
    gdf_region = gpd.read_parquet(file_path)

    # Strip down to only essential columns immediately
    essential_cols = [
        "geometry",
        "REGION",
        "GRP",
        "SUBGRP",
        "POPULATION",
        "geo_code",
        "SUB_REGION",
    ]
    gdf_region = gdf_region[
        [col for col in essential_cols if col in gdf_region.columns]
    ]
    return gdf_region


@st.cache_data(persist="disk")
def load_csv_data():
    """Loads the risk attribute files and handles float32 downcasting."""
    oac_tobacco = pd.read_csv("Gambling_tobacco_OAC_combined.csv")
    oac_tobacco.columns = oac_tobacco.columns.str.strip()

    oac_alcohol = pd.read_csv("Gambling_alcohol_OAC_combined.csv")
    oac_alcohol.columns = oac_alcohol.columns.str.strip()

    numeric_targets = [
        "Mean_OddsRatio_All",
        "OddsRatio_CI_lower_All",
        "OddsRatio_CI_upper_All",
    ]
    for col in numeric_targets:
        if col in oac_tobacco.columns:
            oac_tobacco[col] = oac_tobacco[col].astype("float32")
        if col in oac_alcohol.columns:
            oac_alcohol[col] = oac_alcohol[col].astype("float32")

    return oac_tobacco, oac_alcohol


@st.cache_data(persist="disk")
def build_gdf(
    region: str,
    level: str,
    analysis_type: str,
    top_percentage_tier: int,
) -> gpd.GeoDataFrame:
    """Combines spatial chunks with attributes and applies visual ranking."""
    # Read the tiny regional parquet file instead of the whole country
    g = load_regional_spatial_data(region).copy()
    oac_tobacco, oac_alcohol = load_csv_data()

    shp_col = "GRP" if level == "group" else "SUBGRP"

    def process_oac_file(df, prefix):
        df_filtered = df[df["level"].str.lower() == level.lower()].copy()
        df_filtered["join_key"] = (
            df_filtered["Modified_OA_class_3"].astype(str).str.upper()
        )

        cols = [
            "join_key",
            "Mean_OddsRatio_All",
            "OddsRatio_CI_lower_All",
            "OddsRatio_CI_upper_All",
        ]
        df_sliced = df_filtered[cols].copy()

        return df_sliced.rename(
            columns={
                "Mean_OddsRatio_All": f"{prefix}_OR",
                "OddsRatio_CI_lower_All": f"{prefix}_lower",
                "OddsRatio_CI_upper_All": f"{prefix}_upper",
            }
        )

    tobacco_processed = process_oac_file(oac_tobacco, "tobacco")
    alcohol_processed = process_oac_file(oac_alcohol, "alcohol")

    g["OAC Group Code"] = g["GRP"].str.upper()
    g["OAC Subgroup Code"] = g["SUBGRP"].str.upper()
    g["OAC Group Name"] = (
        g["OAC Group Code"].map(oac_group_names).fillna("Unknown Group")
    )
    g["OAC Subgroup Name"] = (
        g["OAC Subgroup Code"].map(oac_subgroup_names).fillna("Unknown Subgroup")
    )

    g["join_key"] = g[shp_col].str.upper()

    # Splicing datasets
    g = g.merge(tobacco_processed, on="join_key", how="left")
    g = g.merge(alcohol_processed, on="join_key", how="left")
    g = g.drop(columns=["join_key"])

    # Establish risk baseline mapping rule
    if analysis_type == "Tobacco":
        g["active_display_ratio"] = g["tobacco_OR"]
    elif analysis_type == "Alcohol":
        g["active_display_ratio"] = g["alcohol_OR"]
    else:
        g["active_display_ratio"] = (g["tobacco_OR"] + g["alcohol_OR"]) / 2.0

    # Color mapping calculations
    vals = g["active_display_ratio"].fillna(1.0)
    vmin = vals.min()
    vmax = vals.quantile(0.95)

    range_val = vmax - vmin if (vmax - vmin) > 0 else 1.0
    normalized = ((vals - vmin) / range_val).clip(0, 1).fillna(0.5)

    cmap = cm.get_cmap("RdYlGn_r")
    rgba_array = cmap(normalized.to_numpy())

    percentile_needed = 1.0 - (top_percentage_tier / 10.0)
    cutoff_score = vals.quantile(percentile_needed)

    color_list = []
    status_list = []
    for score, row in zip(vals, rgba_array):
        if score >= cutoff_score:
            r = int(row[0] * 255)
            g_val = int(row[1] * 255)
            b = int(row[2] * 255)
            color_list.append([r, g_val, b, 200])
            status_list.append(f"Yes (Top {top_percentage_tier * 10}%)")
        else:
            color_list.append([220, 225, 230, 80])
            status_list.append("Muted (Below selection threshold)")

    g["fill_color"] = color_list
    g["High Risk Alert"] = status_list
    g = g.rename(columns=RENAME_MAP)

    # Force strict 2-decimal rounding as strings right before serialization
    cols_to_format = [
        "tobacco_OR",
        "tobacco_lower",
        "tobacco_upper",
        "alcohol_OR",
        "alcohol_lower",
        "alcohol_upper",
        "active_display_ratio",
    ]
    for c in cols_to_format:
        if c in g.columns:
            g[c] = g[c].apply(
                lambda v: f"{v:.2f}"
                if pd.notnull(v) and isinstance(v, (int, float, np.number))
                else "N/A"
            )

    return g


def build_geojson(gdf: gpd.GeoDataFrame, precision: int = 5) -> dict:
    geoms = gdf.geometry.values
    rounded_geoms = shapely.transform(geoms, lambda c: np.round(c, precision))
    geom_strs = shapely.to_geojson(rounded_geoms)

    prop_cols = [c for c in gdf.columns if c != "geometry"]
    props_records = gdf[prop_cols].to_dict("records")

    features = []
    for gs, pr in zip(geom_strs, props_records):
        features.append(
            {"type": "Feature", "geometry": json.loads(gs), "properties": pr}
        )

    return {"type": "FeatureCollection", "features": features}


def make_deck(gdf: gpd.GeoDataFrame) -> pdk.Deck:
    geojson = build_geojson(gdf)

    layer = pdk.Layer(
        "GeoJsonLayer",
        data=geojson,
        stroked=True,
        filled=True,
        get_fill_color="properties.fill_color",
        get_line_color=[120, 120, 120],
        line_width_min_pixels=0.3,
        pickable=True,
        auto_highlight=True,
    )

    bounds = gdf.total_bounds
    center_lon = (bounds[0] + bounds[2]) / 2
    center_lat = (bounds[1] + bounds[3]) / 2

    view_state = pdk.ViewState(
        longitude=center_lon,
        latitude=center_lat,
        zoom=9,
        pitch=0,
    )

    tooltip_html = (
        "<b>Geographic Info:</b><br/>"
        "&nbsp;&nbsp;OA Code: {Output Area Code}<br/>"
        "&nbsp;&nbsp;Sub-Region: {Sub-Region}<br/>"
        "&nbsp;&nbsp;Region: {Region}<br/>"
        "&nbsp;&nbsp;Population: {Population}<br/>"
        "<hr style='margin: 5px 0; border-color: rgba(255,255,255,0.2);'/>"
        "<b>OAC Group:</b> {OAC Group Name} ({OAC Group Code})<br/>"
        "<b>OAC Subgroup:</b> {OAC Subgroup Name} ({OAC Subgroup Code})<br/>"
        "<hr style='margin: 5px 0; border-color: rgba(255,255,255,0.2);'/>"
        "<b>Tobacco Risk Stats:</b><br/>"
        "&nbsp;&nbsp;Odds Ratio: {tobacco_OR}<br/>"
        "&nbsp;&nbsp;95% CI: [{tobacco_lower} - {tobacco_upper}]<br/>"
        "<hr style='margin: 5px 0; border-color: rgba(255,255,255,0.2);'/>"
        "<b>Alcohol Risk Stats:</b><br/>"
        "&nbsp;&nbsp;Odds Ratio: {alcohol_OR}<br/>"
        "&nbsp;&nbsp;95% CI: [{alcohol_lower} - {alcohol_upper}]<br/>"
        "<hr style='margin: 5px 0; border-color: rgba(255,255,255,0.2);'/>"
        "<b>Visual Map Intensity Score:</b> {active_display_ratio}"
    )

    tooltip_config = {
        "html": tooltip_html,
        "style": {
            "backgroundColor": "#1e293b",
            "color": "white",
            "zIndex": "10000",
        },
    }

    return pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        tooltip=tooltip_config,
        map_style="light",
    )


# --- 3. Creating Application Tabs ---
tab1, tab2, tab3 = st.tabs(
    ["Interactive Map", "How to Use", "Acknowledgments & Data"]
)

# ==========================================
#        TAB 1: INTERACTIVE MAP
# ==========================================
with tab1:
    st.markdown(
        """
        This map presents the odds ratio of co-occurring gambling behavior with alcohol and tobacco use across the UK. 
        Areas highlighted in **red** have higher odds for these co-occurring behaviors, indicating locations where stricter gambling venue regulations should be carefully considered.
        """
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        regions = get_region_list()
        region_choice = st.selectbox(
            "Select a UK region to begin:",
            options=regions,
            index=None,
            placeholder="Choose a region...",
        )

    # Session storage tracking to force aggressive garbage cleaning on switch
    if "current_region" not in st.session_state:
        st.session_state["current_region"] = None

    if (
        region_choice is not None
        and region_choice != st.session_state["current_region"]
    ):
        st.session_state["current_region"] = region_choice
        st.cache_data.clear()

    with col2:
        analysis_choice = st.radio(
            "Select Risk Factor Profile view:",
            options=["Combined Effect", "Tobacco", "Alcohol"],
            index=0,
            horizontal=True,
            disabled=(region_choice is None),
        )

    with col3:
        oac_level_choice = st.radio(
            "Select OAC Resolution Level:",
            options=["Group", "Subgroup"],
            index=1,
            horizontal=True,
            disabled=(region_choice is None),
        )

    if region_choice is not None:
        st.write("")
        risk_slider = st.slider(
            "Show Only the Highest Risk Areas (Risk Focus Filter):",
            min_value=1,
            max_value=10,
            value=10,
            step=1,
        )

        if risk_slider == 10:
            st.markdown(
                "🔍 **Showing 100% of areas** (Full regional landscape, no filtering)."
            )
        else:
            st.markdown(
                f"🔍 **Showing only the Top {risk_slider * 10}% highest-risk areas**."
            )
    else:
        risk_slider = 10

    if region_choice is None:
        st.info(
            "Select a region above to start the risk assessment map environment visualization."
        )
    else:
        level_key = oac_level_choice.lower()

        gdf = build_gdf(
            region_choice,
            level_key,
            analysis_choice,
            risk_slider,
        )
        st.caption(
            f"Showing {len(gdf):,} sectors in {region_choice} analyzing: {analysis_choice} ({oac_level_choice})"
        )

        deck = make_deck(gdf)
        st.pydeck_chart(deck, height=700)


# ==========================================
#        TAB 2: HOW TO USE
# ==========================================
with tab2:
    st.header("How to Use This Dashboard")
    st.write(
        "This interactive dashboard serves as a digital supplement to our research paper..."
    )

# ==========================================
#   TAB 3: ACKNOWLEDGMENTS & DATA AVAILABILITY
# ==========================================
with tab3:
    st.header("Acknowledgments & Data Availability")
    st.subheader("Funding & Support")
    st.write(
        "This research is supported by the EPSRC Centre for Doctoral Training in..."
    )

# --- 4. Global Footnote Section ---
st.write("---")
st.markdown(
    """
    <small style="color: #64748b; line-height: 1.4;">
    <b>Citation Note:</b> These results are derived from the following research paper:<br/>
    Ognayn Simeonov, Benjamin D. Goddard, Jamie Pearce, Valerio Restocchi. 
    <i>Co-occurring patterns of gambling, alcohol and tobacco use should inform gambling cumulative impact assessments in the UK</i>, 
    Harm Reduction Journal (2026).<br/>
    <b>Contact & Inquiries:</b> <a href="mailto:ognyan99@gmail.com">o@gmail.com</a>
    </small>
    """,
    unsafe_allow_html=True,
)
