import streamlit as st
import ee
import pandas as pd
import folium
import json
from datetime import date

# geemap ni standart usulda xavfsiz import qilamiz
try:
    import geemap
    USE_GEEMAP = True
except Exception as e:
    st.error(f"geemap yuklanmadi: {e}")
    USE_GEEMAP = False

# Sahifa sozlamalari
st.set_page_config(
    page_title="Xorazm Meliorativ Monitoring",
    page_icon="🌱",
    layout="wide",
)

# Sidebar dizayni
st.markdown("""
<style>
[data-testid="stSidebar"] {
    background: #1a2e1a;
}
[data-testid="stSidebar"] * {
    color: #d4e8c2 !important;
}
</style>
""", unsafe_allow_html=True)

# GEE init
@st.cache_resource
def init_gee():
    try:
        key_data = dict(st.secrets["earth_engine"])
        key_data["type"] = "service_account"

        credentials = ee.ServiceAccountCredentials(
            email=key_data["client_email"],
            key_data=json.dumps(key_data),
        )

        ee.Initialize(credentials, project=key_data.get("project_id", ""))
        return True

    except Exception as ex:
        st.error(f"GEE ulanishda xato: {ex}")
        return False

gee_ok = init_gee()

# Tumanlar
DISTRICTS = [
    "Urganch", "Xiva", "Shovot", "Bog'ot", "Gurlan",
    "Xonqa", "Qo'shko'pir", "Yangibozor", "Hazorasp",
    "Yangiariq", "Tuproqqal'a", "Pitnak",
]

# Koordinatalar
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

# NDVI holati
def ndvi_class(val):
    if val is None:
        return "⚪ Aniqlanmadi"
    if val < 0.15:
        return "🔴 Yomon"
    elif val < 0.35:
        return "🟡 O'rtacha"
    else:
        return "🟢 Yaxshi"

# Sidebar
with st.sidebar:

    st.markdown("## 🌿 Boshqaruv Paneli")

    st.markdown("---")

    st.markdown("### 📅 Sana")

    col1, col2 = st.columns(2)

    with col1:
        start_date = st.date_input(
            "Boshlanish",
            value=date(2025, 1, 1)
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
        default=["Urganch", "Xiva", "Gurlan"]
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

# Title
st.markdown("# 🌱 Xorazm Viloyati Meliorativ Monitoring")
st.caption("Sentinel-2 · Google Earth Engine · NDVI")

# GEE tekshiruv
if not gee_ok:
    st.warning("⚠️ GEE ulanmagan")
    st.stop()

if not run_btn:
    st.info("👈 Chap paneldan parametrlarni tanlang")
    st.stop()

if not selected_districts:
    st.warning("Kamida bitta tuman tanlang")
    st.stop()

start_str = start_date.strftime("%Y-%m-%d")
end_str = end_date.strftime("%Y-%m-%d")

# Cache key
df_key = f"{start_str}_{end_str}_{cloud_pct}"

# GEE analysis
if df_key not in st.session_state:

    with st.spinner("🛰️ Tahlil qilinmoqda..."):

        try:

            s2 = (
                ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
                .filterDate(start_str, end_str)
                .filterBounds(
                    ee.Geometry.BBox(59.5, 41.0, 61.5, 42.2)
                )
                .filter(
                    ee.Filter.lt(
                        "CLOUDY_PIXEL_PERCENTAGE",
                        cloud_pct
                    )
                )
                .map(
                    lambda img:
                    img.normalizedDifference(["B8", "B4"])
                    .rename("NDVI")
                    .copyProperties(img, ["system:time_start"])
                )
            )

            count = s2.size().getInfo()

            st.write(f"📡 {count} ta tasvir topildi")

            if count == 0:
                st.error("Tasvir topilmadi")
                st.stop()

            median_ndvi = s2.median()

            results = []

            for dist in selected_districts:

                lat, lon = DISTRICT_COORDS[dist]

                point = ee.Geometry.Point([lon, lat])

                try:

                    val = median_ndvi.reduceRegion(
                        reducer=ee.Reducer.mean(),
                        geometry=point.buffer(5000),
                        scale=100,
                        maxPixels=1e9,
                    ).getInfo().get("NDVI")

                except:
                    val = None

                results.append({
                    "Tuman": dist,
                    "NDVI": round(val, 4) if val else None,
                    "Lat": lat,
                    "Lon": lon
                })

            df = pd.DataFrame(results)

            st.session_state[df_key] = df
            st.session_state[f"median_{df_key}"] = median_ndvi

        except Exception as e:
            st.error(f"Xato: {e}")
            st.stop()

# Data
df = st.session_state[df_key]
median_ndvi = st.session_state[f"median_{df_key}"]

# Metrics
st.markdown("## 📊 Ko'rsatkichlar")

valid = df["NDVI"].dropna()

c1, c2, c3, c4 = st.columns(4)

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

# Xarita
st.markdown("## 🗺️ Interaktiv Xarita")

if USE_GEEMAP:

    try:

        Map = geemap.Map(
            center=[41.55, 60.63],
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
            ],
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

        # MARKERS
        for _, row in df.iterrows():

            ndvi_val = row["NDVI"]

            if ndvi_val is None:
                popup_text = f"""
                <b>{row['Tuman']}</b><br>
                NDVI: Aniqlanmadi
                """

            elif ndvi_val < 0.15:
                popup_text = f"""
                <b>{row['Tuman']}</b><br>
                NDVI: {ndvi_val:.3f}<br>
                🔴 Yomon
                """

            elif ndvi_val < 0.35:
                popup_text = f"""
                <b>{row['Tuman']}</b><br>
                NDVI: {ndvi_val:.3f}<br>
                🟡 O'rtacha
                """

            else:
                popup_text = f"""
                <b>{row['Tuman']}</b><br>
                NDVI: {ndvi_val:.3f}<br>
                🟢 Yaxshi
                """

            # FIXED POPUP
            Map.add_marker(
                location=[row["Lat"], row["Lon"]],
                popup=folium.Popup(
                    popup_text,
                    max_width=300
                ),
            )

        st.components.v1.html(
            Map._repr_html_(),
            height=600
        )

    except Exception as e:
        st.error(f"Xarita xatosi: {e}")

# Jadval
st.markdown("## 📋 Jadval")

df["Holat"] = df["NDVI"].apply(ndvi_class)

st.dataframe(
    df[["Tuman", "NDVI", "Holat"]],
    use_container_width=True,
    hide_index=True
)

# Grafik
st.markdown("## 📈 NDVI Grafik")

chart_df = df[["Tuman", "NDVI"]].set_index("Tuman")

st.bar_chart(chart_df)

# Download
st.markdown("## ⬇️ Yuklab olish")

col1, col2 = st.columns(2)

col1.download_button(
    "📥 CSV",
    data=df.to_csv(index=False),
    file_name="ndvi.csv",
    mime="text/csv"
)

col2.download_button(
    "📥 JSON",
    data=df.to_json(
        orient="records",
        force_ascii=False
    ),
    file_name="ndvi.json",
    mime="application/json"
)

st.caption(
    f"📡 Sentinel-2 | {start_str} → {end_str}"
)
