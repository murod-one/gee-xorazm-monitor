import streamlit as st
import ee
import geemap.foliumap as geemap
import pandas as pd
import json
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
from datetime import date, timedelta
import io

# ─── Sahifa sozlamalari ───────────────────────────────────────────────────────
st.set_page_config(
    page_title="Xorazm Meliorativ Monitoring",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── CSS ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  [data-testid="stSidebar"] { background: #1a2e1a; }
  [data-testid="stSidebar"] * { color: #d4e8c2 !important; }
  h1 { color: #2d6a2d; }
  .metric-box {
      background: #f0f7ec;
      border-left: 4px solid #4caf50;
      padding: 12px 16px;
      border-radius: 6px;
      margin: 6px 0;
  }
  .bad-land  { border-left-color: #e53935; background: #fdecea; }
  .mid-land  { border-left-color: #fb8c00; background: #fff3e0; }
  .good-land { border-left-color: #43a047; background: #f1f8e9; }
  .stDownloadButton > button { background:#2d6a2d; color:white; border:none; }
  footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ─── GEE autentifikatsiya ─────────────────────────────────────────────────────
@st.cache_resource
def init_gee():
    try:
        key_data = dict(st.secrets["earth_engine"])
        # private_key ichidagi \\n ni haqiqiy newline ga o'girish
        if "private_key" in key_data:
            key_data["private_key"] = key_data["private_key"].replace("\\n", "\n")
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

# ─── Xorazm tumanlar ro'yxati ─────────────────────────────────────────────────
DISTRICTS = [
    "Urganch", "Xiva", "Shovot", "Bog'ot", "Gurlan",
    "Xonqa", "Qo'shko'pir", "Yangibozor", "Hazorasp",
    "Yangiariq", "Tuproqqal'a", "Pitnak",
]

# Tuman koordinatalari (markaz nuqtalari, taxminiy)
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

def ndvi_class(val):
    if val is None:
        return "Aniqlanmadi", "mid-land"
    if val < 0.15:
        return "🔴 Yomon (meliorativ muammo)", "bad-land"
    elif val < 0.35:
        return "🟡 O'rtacha", "mid-land"
    else:
        return "🟢 Yaxshi", "good-land"

# ─── Sidebar ─────────────────────────────────────────────────────────────────
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
        "Tanlang",
        DISTRICTS,
        default=["Urganch", "Xiva", "Gurlan"],
    )

    st.markdown("### 🗺️ Vizualizatsiya")
    viz_type = st.radio("Tur", ["NDVI xaritasi", "Choropleth", "Marker"])

    cloud_pct = st.slider("☁️ Bulutlilik chegarasi (%)", 0, 100, 20)

    st.markdown("---")
    run_btn = st.button("▶ Tahlil boshlash", use_container_width=True)

# ─── Asosiy kontent ───────────────────────────────────────────────────────────
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

# ─── GEE hisoblash ───────────────────────────────────────────────────────────
start_str = start_date.strftime("%Y-%m-%d")
end_str   = end_date.strftime("%Y-%m-%d")

with st.spinner("🛰️ GEE ma'lumotlari yuklanmoqda..."):

    # Sentinel-2 tasvirlar to'plami
    s2 = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterDate(start_str, end_str)
        .filterBounds(
            ee.Geometry.BBox(59.5, 41.0, 61.5, 42.2)  # Xorazm bbox
        )
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", cloud_pct))
        .map(lambda img: img.normalizedDifference(["B8", "B4"]).rename("NDVI")
                            .copyProperties(img, ["system:time_start"]))
    )

    median_ndvi = s2.median()

    # Har bir tuman uchun o'rtacha NDVI
    results = []
    for dist in selected_districts:
        lat, lon = DISTRICT_COORDS.get(dist, (41.5, 60.5))
        point = ee.Geometry.Point([lon, lat])
        try:
            val = median_ndvi.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=point.buffer(15000),   # 15 km radius
                scale=20,
                maxPixels=1e9,
            ).getInfo().get("NDVI")
        except Exception:
            val = None
        results.append({"Tuman": dist, "NDVI": round(val, 4) if val else None,
                         "Lat": lat, "Lon": lon})

    df = pd.DataFrame(results)

# ─── Metrikalar ──────────────────────────────────────────────────────────────
st.markdown("## 📊 Umumiy Ko'rsatkichlar")
valid = df["NDVI"].dropna()
c1, c2, c3, c4 = st.columns(4)
c1.metric("O'rtacha NDVI", f"{valid.mean():.3f}" if len(valid) else "—")
c2.metric("Maksimal",       f"{valid.max():.3f}"  if len(valid) else "—")
c3.metric("Minimal",        f"{valid.min():.3f}"  if len(valid) else "—")
bad_count = (valid < 0.15).sum()
c4.metric("🔴 Muammoli tumanlar", bad_count)

st.markdown("---")

# ─── Xarita ──────────────────────────────────────────────────────────────────
st.markdown("## 🗺️ Interaktiv Xarita")
Map = geemap.Map(center=[41.55, 60.63], zoom=9)
Map.add_basemap("HYBRID")

ndvi_vis = {
    "min": -0.1, "max": 0.7,
    "palette": ["#d73027","#fc8d59","#fee08b","#d9ef8b","#91cf60","#1a9850"],
}
Map.addLayer(median_ndvi.clip(ee.Geometry.BBox(59.5,41.0,61.5,42.2)),
             ndvi_vis, "NDVI (Sentinel-2)")
Map.add_colorbar(ndvi_vis, label="NDVI", orientation="horizontal", transparent_bg=True)

# Markerlar
for _, row in df.iterrows():
    label, _ = ndvi_class(row["NDVI"])
    ndvi_str = f"{row['NDVI']:.3f}" if row["NDVI"] else "—"
    Map.add_marker(
        location=[row["Lat"], row["Lon"]],
        popup=f"<b>{row['Tuman']}</b><br>NDVI: {ndvi_str}<br>{label}",
    )

Map.to_streamlit(height=520)

# ─── Jadval ──────────────────────────────────────────────────────────────────
st.markdown("## 📋 Tuman Ma'lumotlari")

def colorize_row(row):
    _, cls = ndvi_class(row["NDVI"])
    color_map = {"bad-land": "#fdecea", "mid-land": "#fff3e0", "good-land": "#f1f8e9"}
    bg = color_map.get(cls, "white")
    return [f"background-color: {bg}"] * len(row)

df_display = df[["Tuman", "NDVI"]].copy()
df_display["Holat"] = df["NDVI"].apply(lambda v: ndvi_class(v)[0])
st.dataframe(
    df_display.style.apply(colorize_row, axis=1),
    use_container_width=True,
    hide_index=True,
)

# ─── Grafik ──────────────────────────────────────────────────────────────────
st.markdown("## 📈 NDVI Taqqoslash")
fig, ax = plt.subplots(figsize=(10, 4))
colors = []
for v in df["NDVI"]:
    if v is None:       colors.append("#9e9e9e")
    elif v < 0.15:      colors.append("#e53935")
    elif v < 0.35:      colors.append("#fb8c00")
    else:               colors.append("#43a047")

ax.bar(df["Tuman"], df["NDVI"].fillna(0), color=colors, edgecolor="white", linewidth=0.8)
ax.axhline(0.15, color="#e53935", linestyle="--", linewidth=1, label="Muammo chegarasi (0.15)")
ax.axhline(0.35, color="#fb8c00", linestyle="--", linewidth=1, label="O'rtacha/yaxshi (0.35)")
ax.set_ylabel("NDVI qiymati")
ax.set_title("Tumanlar bo'yicha NDVI taqqoslash")
ax.legend(fontsize=9)
ax.set_ylim(0, 0.8)
plt.xticks(rotation=25, ha="right", fontsize=9)
st.pyplot(fig)

# ─── Yuklab olish ────────────────────────────────────────────────────────────
st.markdown("## ⬇️ Ma'lumotlarni Yuklab Olish")
col_csv, col_json = st.columns(2)

csv_buf = io.StringIO()
df_display.to_csv(csv_buf, index=False)
col_csv.download_button(
    "📥 CSV yuklab olish",
    data=csv_buf.getvalue(),
    file_name=f"xorazm_ndvi_{start_str}_{end_str}.csv",
    mime="text/csv",
)

col_json.download_button(
    "📥 JSON yuklab olish",
    data=df_display.to_json(orient="records", force_ascii=False),
    file_name=f"xorazm_ndvi_{start_str}_{end_str}.json",
    mime="application/json",
)

st.markdown("---")
st.caption(f"📡 Ma'lumot manbai: Sentinel-2 SR · GEE · Tahlil davri: {start_str} → {end_str}")
