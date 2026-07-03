import os
import pydeck as pdk
import streamlit as st

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

    # UI Row Layout
    ui_col1, ui_col2, ui_col3 = st.columns([2, 2, 3])
    
    with ui_col1:
        analysis_choice = st.radio(
            "Select Risk Profile map view layer style:", 
            options=["Combined Effect", "Tobacco", "Alcohol"], 
            horizontal=True,
            help="• Combined Effect: Average risk calculation of both substances.\n• Tobacco: Isolated Tobacco smoking odds ratio risks.\n• Alcohol: Isolated hazardous Alcohol consumption odds ratio risks."
        )
        
    with ui_col2:
        granularity_choice = st.segmented_control(
            "Select OAC Classification Granularity Level:",
            options=["Subgroup", "Group"],
            default="Subgroup",
            help="• Subgroup: Deepest classification granularity (e.g., 4a3 'Hard-Pressed Ethnic Mix').\n• Group: Broader classification level (e.g., 4a 'Hard-Pressed Living')."
        )
        
    with ui_col3:
        percentile_tier = st.slider(
            "Filter Co-occurring Risk Threshold:",
            min_value=1,
            max_value=10,
            value=10,
            step=1,
            help="Slide down to narrow the map view down to only show the most critical, high-risk vulnerability clusters. Lower values isolate the highest percentiles."
        )
        if percentile_tier == 10:
            st.caption("✨ **Currently showing: All Areas**")
        else:
            st.caption(f"🎯 **Currently showing: Top {percentile_tier}0% Highest Risk Areas Only**")

    # 1. Resolve column targets and appropriate percentile threshold bounds
    property_key = "comb_OR"
    scale_key = "sub_95th"
    
    if analysis_choice == "Tobacco":
        property_key = "tob_OR"
    elif analysis_choice == "Alcohol":
        property_key = "alc_OR"
        
    if granularity_choice == "Group":
        scale_key = "grp_95th"
        if property_key != "comb_OR":
            property_key = f"{property_key}_group"
        else:
            property_key = "comb_OR_group"

    # Drops cutoff safely to 0.0 when slider is 10 so green areas are not filtered out
    if percentile_tier == 10:
        risk_cutoff_expr = 0.0
    else:
        risk_cutoff_expr = 1.0 + (10 - percentile_tier) * 0.08

    tile_url =  "/app/static/tiles/{z}/{x}/{y}.mvt"

    # FIXED: Reverted back to clean math expressions without function calls to satisfy the JSON parser
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

    view_state = pdk.ViewState(
        longitude=-3.4360, 
        latitude=55.3781, 
        zoom=5.5, 
        pitch=0
    )

    tooltip_html = (
        "<b>Geographic Info:</b><br/>"
        "&nbsp;&nbsp;OA Code: {geo_code}<br/>"
        "&nbsp;&nbsp;Sub-Region: {SUB_REGION}<br/>"
        "&nbsp;&nbsp;Region: {REGION}<br/>"
        "&nbsp;&nbsp;Population: {POPULATION}<br/>"
        "<hr style='margin: 5px 0; border-color: rgba(255,255,255,0.2);'/>"
        "<b>OAC Classification:</b><br/>"
        "&nbsp;&nbsp;Group: {OAC_Group_Name} ({OAC_Group_Code})<br/>"
        "&nbsp;&nbsp;Subgroup: {OAC_Subgroup_Name} ({OAC_Subgroup_Code})<br/>"
        "<hr style='margin: 5px 0; border-color: rgba(255,255,255,0.2);'/>"
    )
    
    if granularity_choice == "Subgroup":
        tooltip_html += (
            "<b>Selected Level: Subgroup</b><br/>"
            "&nbsp;&nbsp;Tobacco OR: {tob_OR}<br/>"
            "&nbsp;&nbsp;95% CI: [{tob_lower} - {tob_upper}]<br/>"
            "&nbsp;&nbsp;Alcohol OR: {alc_OR}<br/>"
            "&nbsp;&nbsp;95% CI: [{alc_lower} - {alc_upper}]<br/>"
            "&nbsp;&nbsp;Combined Value: <b>{comb_OR}</b>"
        )
    else:
        tooltip_html += (
            "<b>Selected Level: Group</b><br/>"
            "&nbsp;&nbsp;Tobacco OR: {tob_OR_group}<br/>"
            "&nbsp;&nbsp;95% CI: [{tob_lower_group} - {tob_upper_group}]<br/>"
            "&nbsp;&nbsp;Alcohol OR: {alc_OR_group}<br/>"
            "&nbsp;&nbsp;95% CI: [{alc_lower_group} - {alc_upper_group}]<br/>"
            "&nbsp;&nbsp;Combined Value: <b>{comb_OR_group}</b>"
        )

    deck = pdk.Deck(
        layers=[mvt_layer],
        initial_view_state=view_state,
        tooltip={"html": tooltip_html, "style": {"backgroundColor": "#1e293b", "color": "white"}},
        map_style="light",
    )

    st.pydeck_chart(deck, height=750)

with tab2:
    st.header("How to Use This Dashboard")
    st.write("This interactive dashboard serves as a digital supplement to our research paper...")

with tab3:
    st.header("Acknowledgments & Data Availability")
    st.subheader("Funding & Support")
    st.write("This research is supported by the EPSRC Centre for Doctoral Training in Mathematical Modelling, Analysis and Computation (MAC-MIGS), funded by the UK Engineering and Physical Sciences Research Council (Grant EP/S023291/1), the University of Edinburgh, and Heriot-Watt University.")

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
