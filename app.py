# ==============================
# XORAZM NDVI MONITORING SYSTEM
# ==============================

import streamlit as st
import ee
import pandas as pd
import folium
import geemap.foliumap as geemap
import json
from datetime import date

# =========================================
# PAGE CONFIG
# =========================================

st.set_page_config(
    page_title="Xorazm Meliorativ Monitoring",
    page_icon="🌱",
    layout="wide"
)

# =========================================
# SIDEBAR STYLE
# =========================================

st.markdown("""
<style>

[data-testid="stSidebar"]{
    background: linear-gradient(180deg,#0f2d0f,#163d16);
}

[data-testid="stSidebar"] *{
    color:white !important;
}

.stButton button{
    border-radius:10px;
    border:2px solid #2ecc71;
    background:#1f3b1f;
    color:white;
    font-weight:bold;
}

</style>
""", unsafe_allow_html=True)

# =========================================
# GEE INIT
# =========================================

@st.cache_resource
def init_gee():

    try:

        key_data = dict(st.secrets["earth_engine"])

        key_data["type"] = "service_account"

        credentials = ee.ServiceAccountCredentials(
            email=key_data["client_email"],
            key_data=json.dumps(key_data)
        )

        ee.Initialize(
            credentials,
            project=key_data.get("project_id", "")
        )

        return True

    except Exception as e:

        st.error(f"GEE xato: {e}")

        return False


gee_ok = init_gee()

# =========================================
# DISTRICTS
# =========================================

DISTRICT_COORDS = {

    "Urganch":      (41.550, 60.633),
    "Xiva":         (41.378, 60.363),
    "Shovot":       (41.500, 60.400),
    "Bog'ot":       (41.350, 60.183),
    "Gurlan":       (41.850, 60.383),
    "Xonqa":        (41.533, 60.800),
    "Qo'shko'pir":  (41.483, 60.167),
    "Yangibozor":   (41.733, 60.550),
    "Hazorasp":     (41.317, 61.067),
    "Yangiariq":    (41.700, 60.700),
    "Tuproqqal'a":  (41.883, 60.083),
    "Pitnak":       (41.133, 61.133),

}

DISTRICTS = list(DISTRICT_COORDS.keys())

# =========================================
# NDVI STATUS
# =========================================

def ndvi_status(val):

    if val is None:
        return "⚪ Aniqlanmadi"

    if val < 0.15:
        return "🔴 Yomon"

    elif val < 0.35:
        return "🟡 O'rtacha"

    else:
        return "🟢 Yaxshi"

# =========================================
# SIDEBAR
# =========================================

with st.sidebar:

    st.markdown("## 🌿 Boshqaruv Paneli")

    st.markdown("---")

    st.markdown("### 📅 Sana")

    col1, col2 = st.columns(2)

    with col1:

        start_date = st.date_input(
            "Boshlanish",
            value=date(2025,1,1)
        )

    with col2:

        end_date = st.date_input(
            "Tugash",
            value=date.today()
        )

    st.markdown("### 🏘️ Tumanlar")

    selected_districts = st.multiselect(
        "Tanlang",
        DISTRICTS,
        default=["Urganch","Xiva","Gurlan"]
    )

    cloud_pct = st.slider(
        "☁️ Bulutlilik (%)",
        0,
        100,
        50
    )

    run_btn = st.button(
        "▶ Tahlil boshlash",
        use_container_width=True
    )

# =========================================
# TITLE
# =========================================

st.markdown("# 🌱 Xorazm Viloyati Meliorativ Monitoring")

st.caption("Sentinel-2 • Google Earth Engine • NDVI")

# =========================================
# CHECKS
# =========================================

if not gee_ok:

    st.warning("GEE ulanmagan")

    st.stop()

if not run_btn:

    st.info("👈 Parametrlarni tanlang")

    st.stop()

if not selected_districts:

    st.warning("Kamida 1 ta tuman tanlang")

    st.stop()

# =========================================
# DATE
# =========================================

start_str = start_date.strftime("%Y-%m-%d")

end_str = end_date.strftime("%Y-%m-%d")

# =========================================
# GEE ANALYSIS
# =========================================

with st.spinner("🛰️ Tahlil qilinmoqda..."):

    try:

        s2 = (

            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")

            .filterDate(start_str, end_str)

            .filterBounds(
                ee.Geometry.BBox(59.5,41.0,61.5,42.2)
            )

            .filter(
                ee.Filter.lt(
                    "CLOUDY_PIXEL_PERCENTAGE",
                    cloud_pct
                )
            )

            .map(

                lambda img:

                img.normalizedDifference(["B8","B4"])

                .rename("NDVI")

            )

        )

        count = s2.size().getInfo()

        st.write(f"📡 {count} ta Sentinel-2 tasvir topildi")

        if count == 0:

            st.error("Tasvir topilmadi")

            st.stop()

        median_ndvi = s2.median()

        results = []

        for dist in selected_districts:

            lat, lon = DISTRICT_COORDS[dist]

            point = ee.Geometry.Point([lon,lat])

            try:

                ndvi_val = median_ndvi.reduceRegion(

                    reducer=ee.Reducer.mean(),

                    geometry=point.buffer(5000),

                    scale=100,

                    maxPixels=1e9

                ).getInfo().get("NDVI")

            except:

                ndvi_val = None

            results.append({

                "Tuman": dist,

                "NDVI": round(ndvi_val,4) if ndvi_val else None,

                "Lat": lat,

                "Lon": lon

            })

        df = pd.DataFrame(results)

    except Exception as e:

        st.error(f"Xato: {e}")

        st.stop()

# =========================================
# METRICS
# =========================================

st.markdown("## 📊 Ko'rsatkichlar")

valid = df["NDVI"].dropna()

c1,c2,c3,c4 = st.columns(4)

c1.metric(
    "O'rtacha NDVI",
    f"{valid.mean():.3f}" if len(valid) else "-"
)

c2.metric(
    "Maksimal",
    f"{valid.max():.3f}" if len(valid) else "-"
)

c3.metric(
    "Minimal",
    f"{valid.min():.3f}" if len(valid) else "-"
)

c4.metric(
    "🔴 Muammoli",
    int((valid < 0.15).sum())
)

st.markdown("---")

# =========================================
# MAP
# =========================================

st.markdown("## 🗺️ Interaktiv Xarita")

try:

    Map = geemap.Map(
        center=[41.55,60.63],
        zoom=8
    )

    Map.add_basemap("HYBRID")

    ndvi_vis = {

        "min": -0.1,

        "max": 0.7,

        "palette": [

            "#d73027",
            "#fc8d59",
            "#fee08b",
            "#d9ef8b",
            "#91cf60",
            "#1a9850"

        ]

    }

    Map.addLayer(

        median_ndvi.clip(
            ee.Geometry.BBox(
                59.5,
                41.0,
                61.5,
                42.2
            )
        ),

        ndvi_vis,

        "NDVI"

    )

    # ==========================
    # MARKERS
    # ==========================

    for _, row in df.iterrows():

        ndvi_val = row["NDVI"]

        if ndvi_val is None:

            color = "gray"

            status = "Aniqlanmadi"

        elif ndvi_val < 0.15:

            color = "red"

            status = "Yomon"

        elif ndvi_val < 0.35:

            color = "orange"

            status = "O'rtacha"

        else:

            color = "green"

            status = "Yaxshi"

        popup_text = f"""
        <b>{row['Tuman']}</b><br>
        NDVI: {ndvi_val}<br>
        Holat: {status}
        """

        # ==========================
        # FIXED MARKER
        # ==========================

        folium.Marker(

            location=[row["Lat"], row["Lon"]],

            popup=popup_text,

            tooltip=row["Tuman"],

            icon=folium.Icon(
                color=color,
                icon="info-sign"
            )

        ).add_to(Map)

    # ==========================
    # SHOW MAP
    # ==========================

    st.components.v1.html(
        Map.to_html(),
        height=650
    )

except Exception as e:

    st.error(f"Xarita xatosi: {e}")

# =========================================
# TABLE
# =========================================

st.markdown("## 📋 Jadval")

df["Holat"] = df["NDVI"].apply(ndvi_status)

st.dataframe(

    df[["Tuman","NDVI","Holat"]],

    use_container_width=True,

    hide_index=True

)

# =========================================
# CHART
# =========================================

st.markdown("## 📈 NDVI Grafik")

chart_df = df[["Tuman","NDVI"]].set_index("Tuman")

st.bar_chart(chart_df)

# =========================================
# DOWNLOAD
# =========================================

st.markdown("## ⬇️ Yuklab olish")

col1,col2 = st.columns(2)

col1.download_button(

    "📥 CSV yuklash",

    data=df.to_csv(index=False),

    file_name="ndvi.csv",

    mime="text/csv"

)

col2.download_button(

    "📥 JSON yuklash",

    data=df.to_json(
        orient="records",
        force_ascii=False
    ),

    file_name="ndvi.json",

    mime="application/json"

)

# =========================================
# FOOTER
# =========================================

st.caption(
    f"📡 Sentinel-2 | {start_str} → {end_str}"
)
