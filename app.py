import streamlit as st
import ee
import pandas as pd
import json
from datetime import date

# geemap importini shartli qilish
try:
    import geemap.foliumap as geemap
    USE_GEEMAP = True
except Exception as e:
    st.warning(f"geemap yuklanmadi: {e}. Folium bilan davom etamiz.")
    import folium
    from streamlit_folium import st_folium
    USE_GEEMAP = False

st.set_page_config(
    page_title="Xorazm Meliorativ Monitoring",
    page_icon="🌱",
    layout="wide",
)

st.markdown("""
<style>
[data-testid="stSidebar"] { background: #1a2e1a; }
[data-testid="stSidebar"] * { color: #d4e8c2 !important; }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def init_gee():
    try:
        key_data = dict(st.secrets["earth_engine"])
        if "private_key" in key_data:
            key_data["private_key"] = key_data["private_key"].replace("\n", "
")
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

DISTRICTS = [
    "Urganch", "Xiva", "Shovot", "Bog'ot", "Gurlan",
    "Xonqa", "Q'oshko'pir", "Yangibozor", "Hazorasp",
    "Yangiariq", "Tuproqqal'a", "Pitnak",
]

DISTRICT_COORDS = {
    "Urganch":      (41.550, 60.633),
    "Xiva":         (41.378, 60.363),
    "Shovot":       (41.500, 60.400),
    "Bog'ot":       (41.350, 60.183),
    "Gurlan":       (41.850, 60.383),
    "Xonqa":        (41.533, 60.800),
    "Q'oshko'pir":  (41.483, 60.167),
    "Yangibozor":   (41.733, 60.550),
    "Hazorasp":     (41.317, 61.067),
    "Yangiariq":    (41.700, 60.700),
    "Tuproqqal'a":  (41.883, 60.083),
    "Pitnak":       (41.133, 61.133),
}

def ndvi_class(val):
    if val is None:
        return "⚪ Aniqlanmadi"
    if val < 0.15:
        return "🔴 Yomon (meliorativ muammo)"
    elif val < 0.35:
        return "🟡 O'rtacha"
    else:
        return "🟢 Yaxshi"

with st.sidebar:
    st.markdown("## 🌿 Boshqaruv Paneli")
    st.markdown("---")
    st.markdown("### 📅 Vaqt oralig'i")
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Boshlanish", value=date(2026, 1, 1))
    with col2:
        end_date = st.date_input("Tugash", value=date.today())
    st.markdown("### 🏘️ Tumanlar")
    selected_districts = st.multiselect(
        "Tanlang", DISTRICTS,
        default=["Urganch", "Xiva", "Gurlan"],
    )
    cloud_pct = st.slider("☁️ Bulutlilik (%)", 0, 100, 20)
    run_btn = st.button("▶ Tahlil boshlash", use_container_width=True)

st.markdown("# 🌱 Xorazm Viloyati — Meliorativ Holat Monitoringi")
st.caption("Sentinel-2 · Google Earth Engine · NDVI asosida")

if not gee_ok:
    st.warning("⚠️ GEE ulanmagan. Streamlit Secrets bo'limiga kalitlarni kiriting.")
    st.stop()

if not run_btn:
    st.info("👈 Chap paneldan vaqt va tumanlarni tanlang, so'ng **▶ Tahlil boshlash** tugmasini bosing.")
    st.stop()

if not selected_districts:
    st.warning("Kamida bitta tuman tanlang.")
    st.stop()

start_str = start_date.strftime("%Y-%m-%d")
end_str   = end_date.strftime("%Y-%m-%d")

with st.spinner("🛰️ GEE ma'lumotlari yuklanmoqda..."):
    s2 = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterDate(start_str, end_str)
        .filterBounds(ee.Geometry.BBox(59.5, 41.0, 61.5, 42.2))
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", cloud_pct))
        .map(lambda img: img.normalizedDifference(["B8", "B4"]).rename("NDVI")
                            .copyProperties(img, ["system:time_start"]))
    )
    median_ndvi = s2.median()

    results = []
    for dist in selected_districts:
        lat, lon = DISTRICT_COORDS.get(dist, (41.5, 60.5))
        point = ee.Geometry.Point([lon, lat])
        try:
            val = median_ndvi.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=point.buffer(15000),
                scale=20,
                maxPixels=1e9,
            ).getInfo().get("NDVI")
        except Exception:
            val = None
        results.append({"Tuman": dist, "NDVI": round(val, 4) if val else None,
                         "Lat": lat, "Lon": lon})

    df = pd.DataFrame(results)

# Metrikalar
st.markdown("## 📊 Umumiy Ko'rsatkichlar")
valid = df["NDVI"].dropna()
c1, c2, c3, c4 = st.columns(4)
c1.metric("O'rtacha NDVI", f"{valid.mean():.3f}" if len(valid) else "—")
c2.metric("Maksimal",       f"{valid.max():.3f}"  if len(valid) else "—")
c3.metric("Minimal",        f"{valid.min():.3f}"  if len(valid) else "—")
c4.metric("🔴 Muammoli tumanlar", int((valid < 0.15).sum()))

st.markdown("---")

# Xarita
st.markdown("## 🗺️ Interaktiv Xarita")

if USE_GEEMAP:
    Map = geemap.Map(center=[41.55, 60.63], zoom=9)
    Map.add_basemap("HYBRID")
    ndvi_vis = {
        "min": -0.1, "max": 0.7,
        "palette": ["#d73027","#fc8d59","#fee08b","#d9ef8b","#91cf60","#1a9850"],
    }
    Map.addLayer(
        median_ndvi.clip(ee.Geometry.BBox(59.5, 41.0, 61.5, 42.2)),
        ndvi_vis, "NDVI (Sentinel-2)"
    )
    for _, row in df.iterrows():
        ndvi_str = f"{row['NDVI']:.3f}" if row["NDVI"] else "—"
        Map.add_marker(
            location=[row["Lat"], row["Lon"]],
            popup=f"<b>{row['Tuman']}</b><br>NDVI: {ndvi_str}<br>{ndvi_class(row['NDVI'])}",
        )
    Map.to_streamlit(height=500)
else:
    # Folium bilan zaxira variant
    m = folium.Map(location=[41.55, 60.63], zoom_start=9, tiles="OpenStreetMap")
    for _, row in df.iterrows():
        color = "red" if row["NDVI"] and row["NDVI"] < 0.15 else "orange" if row["NDVI"] and row["NDVI"] < 0.35 else "green"
        folium.Marker(
            location=[row["Lat"], row["Lon"]],
            popup=f"{row['Tuman']}: NDVI={row['NDVI']:.3f}" if row["NDVI"] else f"{row['Tuman']}: N/A",
            icon=folium.Icon(color=color)
        ).add_to(m)
    st_folium(m, width=700, height=500)

# Jadval
st.markdown("## 📋 Tuman Ma'lumotlari")
df["Holat"] = df["NDVI"].apply(ndvi_class)
st.dataframe(df[["Tuman", "NDVI", "Holat"]], use_container_width=True, hide_index=True)

# Grafik - streamlit native
st.markdown("## 📈 NDVI Taqqoslash")
chart_df = df[["Tuman", "NDVI"]].set_index("Tuman")
st.bar_chart(chart_df)

# Yuklab olish
st.markdown("## ⬇️ Ma'lumotlarni Yuklab Olish")
col_csv, col_json = st.columns(2)
col_csv.download_button(
    "📥 CSV", data=df.to_csv(index=False),
    file_name=f"xorazm_ndvi_{start_str}_{end_str}.csv", mime="text/csv"
)
col_json.download_button(
    "📥 JSON", data=df.to_json(orient="records", force_ascii=False),
    file_name=f"xorazm_ndvi_{start_str}_{end_str}.json", mime="application/json"
)
st.caption(f"📡 Sentinel-2 SR · GEE · {start_str} → {end_str}")
