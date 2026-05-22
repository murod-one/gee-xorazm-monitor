# =========================================================
# Xorazm Viloyati Meliorativ Monitoring
# Streamlit + Folium + GEE + Plotly
# =========================================================

import streamlit as st
import ee
import folium
from streamlit_folium import st_folium

from folium.plugins import (
    HeatMap,
    Draw,
    MeasureControl,
    MiniMap,
    Fullscreen,
    MousePosition
)

import pandas as pd
import numpy as np

from datetime import (
    date,
    datetime
)

import plotly.express as px
import plotly.graph_objects as go

# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(

    page_title="Xorazm Viloyati Meliorativ Monitoring",

    page_icon="🌱",

    layout="wide",

    initial_sidebar_state="expanded"

)

# =========================================================
# STYLE
# =========================================================

st.markdown("""

<style>

.stApp{
    background:
    linear-gradient(
    180deg,
    #081c15,
    #1b4332
    );
}

.main-title{
    font-size:42px;
    font-weight:700;
    text-align:center;
    color:white;
}

.subtitle{
    text-align:center;
    color:#dcdcdc;
    margin-bottom:25px;
}

[data-testid="stSidebar"]{
    background:#081c15;
}

[data-testid="stSidebar"] *{
    color:white !important;
}

.stButton button{

    width:100%;

    border-radius:12px;

    border:1px solid #52b788;

    background:#1b4332;

    color:white;

    font-weight:600;
}

.metric-card{

    background:#1b4332;

    padding:15px;

    border-radius:15px;
}

</style>

""", unsafe_allow_html=True)

# =========================================================
# GEE INIT
# =========================================================

@st.cache_resource
def init_gee():

    try:

        service_account = st.secrets["earth_engine"]["service_account"]

        private_key = st.secrets["earth_engine"]["private_key"]

        project = st.secrets["earth_engine"]["project"]

        credentials = ee.ServiceAccountCredentials(

            service_account,

            key_data=private_key

        )

        ee.Initialize(
            credentials,
            project=project
        )

        return True

    except Exception as e:

        st.error(f"GEE xato: {e}")

        return False

ee_ok = init_gee()

# =========================================================
# DISTRICTS
# =========================================================

DISTRICTS = {

    "Urganch": {
        "center":[41.55,60.63],
        "area":450
    },

    "Xiva": {
        "center":[41.38,60.37],
        "area":380
    },

    "Gurlan": {
        "center":[41.85,60.40],
        "area":320
    },

    "Shovot": {
        "center":[41.65,60.30],
        "area":290
    },

    "Yangiariq": {
        "center":[41.30,60.55],
        "area":410
    },

    "Yangibozor": {
        "center":[41.73,60.55],
        "area":350
    },

    "Xonqa": {
        "center":[41.47,60.78],
        "area":270
    },

    "Bog'ot": {
        "center":[41.35,60.85],
        "area":310
    },

    "Tuproqqal'a": {
        "center":[41.75,61.15],
        "area":520
    },

    "Qo'shko'pir": {
        "center":[41.48,60.16],
        "area":470
    }

}

# =========================================================
# NDVI COLOR
# =========================================================

def get_ndvi_color(ndvi):

    if ndvi < 0.2:
        return "#8B0000"

    elif ndvi < 0.4:
        return "#FF4500"

    elif ndvi < 0.6:
        return "#FFD700"

    elif ndvi < 0.75:
        return "#7CFC00"

    else:
        return "#006400"

# =========================================================
# GEE NDVI URL
# =========================================================

@st.cache_data(ttl=3600)
def get_gee_ndvi_url(

    start_date,

    end_date,

    cloud=20

):

    try:

        xorazm = ee.Geometry.Rectangle(
            [59.8,41.0,61.6,42.1]
        )

        s2 = (

            ee.ImageCollection(
                "COPERNICUS/S2_SR_HARMONIZED"
            )

            .filterBounds(xorazm)

            .filterDate(
                str(start_date),
                str(end_date)
            )

            .filter(
                ee.Filter.lt(
                    "CLOUDY_PIXEL_PERCENTAGE",
                    cloud
                )
            )

        )

        ndvi = s2.map(

            lambda img:

            img.normalizedDifference(
                ["B8","B4"]
            ).rename("NDVI")

        ).median()

        map_id = ndvi.getMapId({

            "min":-0.2,

            "max":0.8,

            "palette":[

                "#8B0000",
                "#FF4500",
                "#FFD700",
                "#7CFC00",
                "#228B22",
                "#006400"

            ]

        })

        return map_id["tile_fetcher"].url_format

    except:
        return None

# =========================================================
# SIMULATION DATA
# =========================================================

@st.cache_data(ttl=1800)
def generate_ndvi_data(

    district,

    start_date,

    end_date

):

    np.random.seed(42)

    dates = pd.date_range(

        start=start_date,

        end=end_date,

        freq='5D'

    )

    base = {

        "Urganch":0.45,
        "Xiva":0.52,
        "Gurlan":0.38,
        "Shovot":0.41,
        "Yangiariq":0.48,
        "Yangibozor":0.43,
        "Xonqa":0.50,
        "Bog'ot":0.35,
        "Tuproqqal'a":0.40,
        "Qo'shko'pir":0.39

    }

    data=[]

    for d in dates:

        month = d.month

        if month in [3,4,5]:

            factor = 1.3

        elif month in [6,7,8]:

            factor = 0.9

        elif month in [9,10]:

            factor = 0.7

        else:

            factor = 0.4

        ndvi = (

            base[district]

            * factor

            + np.random.normal(0,0.05)

        )

        ndvi = max(0.1,min(0.95,ndvi))

        data.append({

            "date":d,

            "district":district,

            "ndvi":round(ndvi,3)

        })

    return pd.DataFrame(data)

# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    st.title("🛰 Boshqaruv Paneli")

    if ee_ok:

        st.success("✅ GEE ulandi")

    else:

        st.error("❌ GEE xato")

    st.markdown("---")

    start_date = st.date_input(

        "📅 Boshlanish",

        value=date(2026,3,1)

    )

    end_date = st.date_input(

        "📅 Tugash",

        value=date.today()

    )

    selected = st.multiselect(

        "🏘 Tumanlar",

        list(DISTRICTS.keys()),

        default=[
            "Urganch",
            "Xiva",
            "Gurlan"
        ]

    )

    cloud = st.slider(

        "☁️ Bulutlilik",

        0,
        100,
        20

    )

    map_type = st.selectbox(

        "🗺 Vizualizatsiya",

        [
            "Real NDVI",
            "Markers",
            "HeatMap",
            "Choropleth"
        ]

    )

# =========================================================
# TITLE
# =========================================================

st.markdown(

    '<div class="main-title">🌱 Xorazm Viloyati Meliorativ Monitoring</div>',

    unsafe_allow_html=True

)

st.markdown(

    '<div class="subtitle">Sentinel-2 • Google Earth Engine • NDVI Monitoring</div>',

    unsafe_allow_html=True

)

# =========================================================
# DATA
# =========================================================

if selected:

    all_data=[]

    for d in selected:

        df = generate_ndvi_data(

            d,

            start_date,

            end_date

        )

        all_data.append(df)

    combined = pd.concat(all_data)

    # =====================================================
    # METRICS
    # =====================================================

    c1,c2,c3,c4 = st.columns(4)

    c1.metric(
        "📊 O'rtacha",
        f"{combined['ndvi'].mean():.3f}"
    )

    c2.metric(
        "🌿 Maksimal",
        f"{combined['ndvi'].max():.3f}"
    )

    c3.metric(
        "🍂 Minimal",
        f"{combined['ndvi'].min():.3f}"
    )

    c4.metric(
        "✅ Sog'lom %",
        f"{(combined['ndvi']>0.6).sum()/len(combined)*100:.1f}%"
    )

# =========================================================
# MAP
# =========================================================

st.markdown("---")

st.subheader("🗺 Interaktiv Xarita")

m = folium.Map(

    location=[41.55,60.60],

    zoom_start=8,

    tiles="CartoDB dark_matter"

)

# =========================================================
# REAL NDVI
# =========================================================

if map_type == "Real NDVI" and ee_ok:

    with st.spinner("🛰 Sentinel-2 yuklanmoqda..."):

        url = get_gee_ndvi_url(

            start_date,

            end_date,

            cloud

        )

        if url:

            folium.TileLayer(

                tiles=url,

                attr="Google Earth Engine",

                name="NDVI",

                overlay=True,

                opacity=0.85

            ).add_to(m)

# =========================================================
# MARKERS
# =========================================================

if map_type == "Markers":

    for d in selected:

        df = generate_ndvi_data(

            d,

            start_date,

            end_date

        )

        latest = df['ndvi'].iloc[-1]

        center = DISTRICTS[d]["center"]

        folium.CircleMarker(

            location=center,

            radius=15 + latest*25,

            popup=f"""

            <b>{d}</b><br>

            NDVI: {latest:.3f}

            """,

            tooltip=d,

            color=get_ndvi_color(latest),

            fill=True,

            fill_opacity=0.7

        ).add_to(m)

# =========================================================
# HEATMAP
# =========================================================

if map_type == "HeatMap":

    heat_data=[]

    for d in selected:

        df = generate_ndvi_data(

            d,

            start_date,

            end_date

        )

        latest = df['ndvi'].iloc[-1]

        center = DISTRICTS[d]["center"]

        for i in range(25):

            heat_data.append([

                center[0] + np.random.normal(0,0.05),

                center[1] + np.random.normal(0,0.05),

                latest * 100

            ])

    HeatMap(

        heat_data,

        radius=25,

        blur=18

    ).add_to(m)

# =========================================================
# CHOROPLETH
# =========================================================

if map_type == "Choropleth":

    for d in selected:

        center = DISTRICTS[d]["center"]

        df = generate_ndvi_data(

            d,

            start_date,

            end_date

        )

        latest = df['ndvi'].iloc[-1]

        folium.Rectangle(

            bounds=[

                [center[0]-0.12,center[1]-0.12],

                [center[0]+0.12,center[1]+0.12]

            ],

            color=get_ndvi_color(latest),

            fill=True,

            fill_opacity=0.5,

            popup=f"{d} | NDVI {latest:.3f}"

        ).add_to(m)

# =========================================================
# MAP TOOLS
# =========================================================

Draw(export=True).add_to(m)

MeasureControl().add_to(m)

MiniMap().add_to(m)

Fullscreen().add_to(m)

MousePosition().add_to(m)

folium.LayerControl().add_to(m)

# =========================================================
# SHOW MAP
# =========================================================

st_folium(

    m,

    width=1400,

    height=650

)

# =========================================================
# TABS
# =========================================================

st.markdown("---")

tab1,tab2,tab3,tab4 = st.tabs([

    "📈 Timeline",

    "📊 Comparison",

    "📋 Data",

    "⬇ Export"

])

# =========================================================
# TIMELINE
# =========================================================

with tab1:

    fig = go.Figure()

    for d in selected:

        df = generate_ndvi_data(

            d,

            start_date,

            end_date

        )

        fig.add_trace(

            go.Scatter(

                x=df["date"],

                y=df["ndvi"],

                mode="lines+markers",

                name=d

            )

        )

    fig.update_layout(

        title="NDVI Timeline",

        height=500,

        yaxis=dict(range=[0,1])

    )

    st.plotly_chart(

        fig,

        use_container_width=True

    )

# =========================================================
# COMPARISON
# =========================================================

with tab2:

    compare=[]

    for d in selected:

        df = generate_ndvi_data(

            d,

            start_date,

            end_date

        )

        compare.append({

            "District":d,

            "Average NDVI":df["ndvi"].mean()

        })

    comp_df = pd.DataFrame(compare)

    fig = px.bar(

        comp_df,

        x="District",

        y="Average NDVI",

        color="Average NDVI",

        color_continuous_scale="YlGn"

    )

    st.plotly_chart(

        fig,

        use_container_width=True

    )

# =========================================================
# TABLE
# =========================================================

with tab3:

    st.dataframe(

        combined,

        use_container_width=True

    )

# =========================================================
# EXPORT
# =========================================================

with tab4:

    csv = combined.to_csv(index=False).encode("utf-8")

    st.download_button(

        "📥 Download CSV",

        csv,

        file_name="xorazm_ndvi.csv",

        mime="text/csv"

    )

# =========================================================
# FOOTER
# =========================================================

st.markdown("---")

st.markdown(

    "<center>🛰 Sentinel-2 | Google Earth Engine | Xorazm GIS Platform</center>",

    unsafe_allow_html=True

)
