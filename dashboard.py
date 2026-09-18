import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from streamlit_autorefresh import st_autorefresh

# Page Setup
st.set_page_config(
    page_title="IoT Edge Telemetry & Hardware Status",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Auto-refresh every 2 seconds so the dashboard actually looks "live" on stage
# (Streamlit normally only re-runs on user interaction, which would make the
# demo look frozen during the network-outage moment.)
st_autorefresh(interval=2000, key="datarefresh")

# Dark Theme CSS
st.markdown("""
    <style>
    .stApp { background-color: #0E1117; color: #FFFFFF; }
    .alert-card { background-color: #3b1111; border: 2px solid #ff4b4b; padding: 10px; border-radius: 8px; margin-bottom: 10px; }
    .offline-banner { background-color: #854d0e; border: 2px solid #eab308; padding: 15px; border-radius: 8px; text-align: center; color: white; font-weight: bold; font-size: 18px; }
    </style>
""", unsafe_allow_html=True)

# Sidebar
st.sidebar.title("Configuration")
BACKEND_URL = st.sidebar.text_input("Backend Base URL", "http://127.0.0.1:8000")
if st.sidebar.button("🔄 Refresh Data"):
    st.rerun()

# Safe API Request Handler
def fetch_api(endpoint):
    try:
        response = requests.get(f"{BACKEND_URL}{endpoint}", timeout=2.0)
        if response.status_code == 200:
            return response.json()
    except Exception:
        return None
    return None

# Fetch Data
device_status = fetch_api("/api/device/status") or {"online": True, "last_seen": "N/A", "buffered_count": 0}
resource_data = fetch_api("/api/resource") or {"cpu_percent": 12, "ram_percent": 45, "power_watts": 0.01}
telemetry_data = fetch_api("/api/telemetry/latest") or []
alerts = fetch_api("/api/alerts") or []

# Header & Network Outage Banner
st.title("🛰️ Iris-Link")

if not device_status.get("online", True):
    st.markdown(
        f"""
        <div class="offline-banner">
            ⚠️ NETWORK OUTAGE DETECTED — EDGE NODE IS BUFFERING TELEMETRY LOCALLY 
            <br/><span style="font-size: 14px;">Buffered Packets: {device_status.get('buffered_count', 0)} | Last Connected: {device_status.get('last_seen')}</span>
        </div>
        """, 
        unsafe_allow_html=True
    )
    st.write("")

# Metrics
col1, col2, col3, col4 = st.columns(4)
col1.metric("Device Connection", "🟢 ONLINE" if device_status.get("online") else "🔴 OFFLINE (BUFFERING)")
col2.metric("Buffered Ring-Buffer", f"{device_status.get('buffered_count', 0)} pkts")
col3.metric("Power Draw", f"{resource_data.get('power_watts', 0):.2f} W")
col4.metric("CPU / RAM Load", f"{resource_data.get('cpu_percent', 0)}% / {resource_data.get('ram_percent', 0)}%")

st.divider()

# Charts & Alerts
col_left, col_right = st.columns([2, 1])

with col_left:
    st.subheader("📈 Real-time Telemetry Streams")
    if telemetry_data:
        df = pd.DataFrame(telemetry_data)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        fig_temp = px.line(df, x='timestamp', y='temperature', title="Temperature (°C)", color_discrete_sequence=["#FF4B4B"])
        fig_temp.update_layout(height=200, margin=dict(l=10, r=10, t=30, b=10), template="plotly_dark")
        st.plotly_chart(fig_temp, use_container_width=True)
        
        fig_vib = px.line(df, x='timestamp', y='vibration', title="Vibration (mm/s)", color_discrete_sequence=["#00D4FF"])
        fig_vib.update_layout(height=200, margin=dict(l=10, r=10, t=30, b=10), template="plotly_dark")
        st.plotly_chart(fig_vib, use_container_width=True)
    else:
        st.info("⚠️ Disconnected from Backend Server. Enter Person C's IP in the sidebar once active.")

with col_right:
    st.subheader("🚨 Anomaly Alerts")
    if alerts:
        for alert in alerts[-3:]:
            st.markdown(
                f"""<div class="alert-card">
                    <strong>⚠️ ANOMALY DETECTED</strong><br/>
                    Temp: {alert.get('temperature')}°C | Vib: {alert.get('vibration')}mm/s
                </div>""", 
                unsafe_allow_html=True
            )
    else:
        st.success("System Nominal — No Active Alerts")
        
    st.write("---")
    st.subheader("🔍 Raw Stream Inspector")
    if telemetry_data:
        latest = telemetry_data[-1]
        status = latest.get("status", "normal")
        if status == "buffered":
            st.warning("⏪ This reading was buffered during an outage and flushed with its original timestamp.")
        elif status == "alert":
            st.error("⚠️ This reading triggered an anomaly alert.")
        st.json(latest)
    else:
        st.caption("No stream data loaded.")