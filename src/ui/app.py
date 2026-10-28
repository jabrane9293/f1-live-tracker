import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.ingestion.openf1_client import OpenF1Client
from src.analytics.lap_metrics import LapAnalyzer, format_lap_time
from src.models.lap_predictor import LapPredictor
from src.agents.strategist_agent import StrategistAgent
from src.agents.anomaly_agent import AnomalyDetectorAgent

st.set_page_config(
    page_title="F1 Live & Replay Center",
    page_icon="🏎️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Instance client unique
@st.cache_resource
def get_client():
    return OpenF1Client()

client = get_client()

# --- SIDEBAR : SELECTION LIVE OU REPLAY ---
st.sidebar.title("🏎️ Session Control")
mode = st.sidebar.radio("Mode d'analyse :", ["Dernière Session / Live", "Replay Historique"])

session_key = None
selected_session_info = None

if mode == "Replay Historique":
    year = st.sidebar.selectbox("Année :", [2026, 2025, 2024, 2023], index=1)
    meetings = client.get_meetings(year=year)
    
    if meetings:
        meeting_options = {m['meeting_official_name']: m['meeting_key'] for m in meetings}
        selected_meeting_name = st.sidebar.selectbox("Grand Prix :", list(meeting_options.keys()))
        meeting_key = meeting_options[selected_meeting_name]
        
        sessions = client.get_sessions(meeting_key=meeting_key)
        if sessions:
            session_options = {f"{s.get('session_name')} ({s.get('session_type')})": s for s in sessions}
            selected_session_label = st.sidebar.selectbox("Séance :", list(session_options.keys()))
            selected_session_info = session_options[selected_session_label]
            session_key = selected_session_info.get("session_key")
else:
    latest = client.get_latest_session()
    if latest:
        session_key = latest.get("session_key")
        selected_session_info = latest

# --- CHARGEMENT DES DONNÉES DE LA SESSION SÉLECTIONNÉE ---
if session_key:
    st.title(f"🏎️ {selected_session_info.get('location', 'F1')} - {selected_session_info.get('session_name', 'Session')}")
    st.caption(f"Circuit: {selected_session_info.get('circuit_short_name')} | Key: {session_key}")

    # Data fetching
    laps_data = client.get_laps(session_key)
    drivers_data = client.get_drivers(session_key)
    weather_data = client.get_weather(session_key)
    race_control = client.get_race_control(session_key)

    analyzer = LapAnalyzer(laps_data, drivers_data)

    # STRUCTURE DES ONGLETS
    tab_lb, tab_telemetry, tab_ai, tab_weather = st.tabs([
        "📊 Leaderboard & Stints", 
        "🗺️ Tracé & Télémétrie 2D", 
        "🤖 Stratégie & IA", 
        "🚩 Météo & Race Control"
    ])

    # --- TAB 1 : LEADERBOARD ---
    with tab_lb:
        st.subheader("Classement des meilleurs temps")
        lb_df = analyzer.get_leaderboard()
        
        if not lb_df.empty:
            st.dataframe(
                lb_df,
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("Aucun chrono enregistré sur cette session.")

        st.subheader("Secteurs Violets (Absolus)")
        purples = analyzer.get_purple_sectors()
        c1, c2, c3 = st.columns(3)
        c1.metric("Secteur 1", purples.get("duration_sector_1", "-"))
        c2.metric("Secteur 2", purples.get("duration_sector_2", "-"))
        c3.metric("Secteur 3", purples.get("duration_sector_3", "-"))

    # --- TAB 2 : TRACÉ & TÉLÉMÉTRIE ---
    with tab_telemetry:
        st.subheader("Carte du circuit et position des monoplaces (X, Y)")
        loc_data = client.get_location(session_key)
        
        if loc_data:
            loc_df = pd.DataFrame(loc_data)
            # Sous-échantillonnage pour fluidité d'affichage
            sample_loc = loc_df.iloc[::5] 
            
            # Map couleur écurie si disponible
            fig_map = px.scatter(
                sample_loc, 
                x='x', 
                y='y', 
                color='driver_number',
                title="Représentation 2D des coordonnées télémétriques",
                labels={'x': 'Position X', 'y': 'Position Y'},
                color_continuous_scale=px.colors.qualitative.Plotly
            )
            fig_map.update_traces(marker=dict(size=4))
            fig_map.update_layout(template="plotly_dark", height=600)
            st.plotly_chart(fig_map, use_container_width=True)
        else:
            st.info("Données de position GPS/Télémétrie indisponibles pour cette séance.")

    # --- TAB 3 : STRATÉGIE & IA ---
    with tab_ai:
        st.subheader("Analyse d'Undercut & Modélisation")
        if laps_data and len(laps_data) > 10:
            predictor = LapPredictor()
            predictor.train(laps_data)
            strategist = StrategistAgent()
            
            drivers_list = sorted(list(set(d['driver_number'] for d in laps_data if 'driver_number' in d)))
            col_a, col_b = st.columns(2)
            d_chase = col_a.selectbox("Pilote Poursuivant :", drivers_list, index=0)
            d_lead = col_b.selectbox("Pilote Devant :", drivers_list, index=min(1, len(drivers_list)-1))

            if d_chase != d_lead:
                delta_df = analyzer.calculate_driver_delta(d_chase, d_lead)
                if not delta_df.empty:
                    alert = strategist.analyze_undercut_opportunity(d_chase, d_lead, delta_df)
                    if alert:
                        st.warning(alert, icon="🚨")

                    fig_delta = px.line(
                        delta_df, 
                        x='lap_number', 
                        y='cumulative_delta',
                        title=f"Écart cumulé (s) : {d_chase} vs {d_lead}"
                    )
                    fig_delta.update_yaxes(autorange="reversed")
                    st.plotly_chart(fig_delta, use_container_width=True)
        else:
            st.info("Données insuffisantes pour l'analyse IA.")

    # --- TAB 4 : MÉTÉO & RACE CONTROL ---
    with tab_weather:
        col_w, col_rc = st.columns(2)
        
        with col_w:
            st.subheader("Conditions Météorologiques")
            if weather_data:
                w_latest = weather_data[-1]
                st.metric("Piste (°C)", f"{w_latest.get('track_temperature')} °C")
                st.metric("Air (°C)", f"{w_latest.get('air_temperature')} °C")
                st.metric("Humidité", f"{w_latest.get('humidity')} %")
                st.metric("Pluie", "Oui 🌧️" if w_latest.get('rainfall') else "Non ☀️")
            else:
                st.write("Aucune donnée météo.")

        with col_rc:
            st.subheader("Direction de course (Race Control)")
            if race_control:
                rc_df = pd.DataFrame(race_control)[['date', 'category', 'message', 'flag']].tail(10)
                st.dataframe(rc_df, use_container_width=True, hide_index=True)
            else:
                st.write("Aucun message de direction de course.")

else:
    st.error("Impossible de récupérer les données de session OpenF1.")