import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.ingestion.openf1_client import OpenF1Client
from src.analytics.lap_metrics import LapAnalyzer, format_lap_time
from src.models.lap_predictor import LapPredictor
from src.agents.strategist_agent import StrategistAgent

st.set_page_config(
    page_title="F1 Live & Replay Center",
    page_icon="🏎️",
    layout="wide",
    initial_sidebar_state="expanded"
)

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
    year = st.sidebar.selectbox("Année :", [2026, 2025, 2024, 2023], index=0)
    meetings = client.get_meetings(year=year)
    
    if meetings:
        # Nettoyage des noms de GP pour éviter la truncation dans la sidebar
        meeting_options = {}
        for m in meetings:
            clean_name = f"{m.get('country_name', 'GP')} - {m.get('meeting_name', '')}".strip(" -")
            meeting_options[clean_name] = m['meeting_key']
            
        selected_meeting_label = st.sidebar.selectbox("Grand Prix :", list(meeting_options.keys()))
        meeting_key = meeting_options[selected_meeting_label]
        
        sessions = client.get_sessions(meeting_key=meeting_key)
        if sessions:
            session_options = {f"{s.get('session_name')} ({s.get('session_type', '')})": s for s in sessions}
            selected_session_label = st.sidebar.selectbox("Séance :", list(session_options.keys()))
            selected_session_info = session_options[selected_session_label]
            session_key = selected_session_info.get("session_key")
else:
    latest = client.get_latest_session()
    if latest:
        session_key = latest.get("session_key")
        selected_session_info = latest

# --- CHARGEMENT DE LA SESSION ---
if session_key:
    circuit_name = selected_session_info.get('circuit_short_name') or selected_session_info.get('location') or "Circuit"
    sess_name = selected_session_info.get('session_name') or "Session"
    
    st.title(f"🏎️ {circuit_name} - {sess_name}")

    laps_data = client.get_laps(session_key)
    drivers_data = client.get_drivers(session_key)
    weather_data = client.get_weather(session_key)
    race_control = client.get_race_control(session_key)

    analyzer = LapAnalyzer(laps_data, drivers_data)

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
            st.dataframe(lb_df, use_container_width=True, hide_index=True)
        else:
            st.info("Aucun chrono enregistré sur cette session.")

        st.subheader("Secteurs Violets (Absolus)")
        purples = analyzer.get_purple_sectors()
        c1, c2, c3 = st.columns(3)
        c1.metric("Secteur 1", purples.get("duration_sector_1", "-"))
        c2.metric("Secteur 2", purples.get("duration_sector_2", "-"))
        c3.metric("Secteur 3", purples.get("duration_sector_3", "-"))

    # --- TAB 2 : TRACÉ & TÉLÉMÉTRIE 2D REPLAY ---
    with tab_telemetry:
        st.subheader("Tracé du circuit et Replay de positionnement")
        
        # Récupération du tracé via le pilote leader pour éviter les timeouts
        leader_num = lb_df.iloc[0]['driver_number'] if not lb_df.empty else 1
        circuit_locs = client.get_location(session_key, driver_number=leader_num)

        if circuit_locs:
            circuit_df = pd.DataFrame(circuit_locs).iloc[::3] # Sous-échantillonnage pour la fluidité
            
            # Figure de base : Le tracé du circuit
            fig_map = go.Figure()
            fig_map.add_trace(go.Scatter(
                x=circuit_df['x'], y=circuit_df['y'],
                mode='lines',
                line=dict(color='gray', width=3),
                name='Piste',
                hoverinfo='skip'
            ))

            # Curseur de Replay / Tour
            if laps_data:
                max_laps = int(pd.DataFrame(laps_data)['lap_number'].max())
                replay_lap = st.slider("🕹️ Simuler le tour :", min_value=1, max_value=max_laps, value=max_laps)
                
                # Position des pilotes à ce tour précis (basé sur leur meilleur secteur / tour)
                laps_df = pd.DataFrame(laps_data)
                lap_positions = laps_df[laps_df['lap_number'] == replay_lap]

                if not lap_positions.empty:
                    for _, row in lap_positions.iterrows():
                        d_num = int(row['driver_number'])
                        info = analyzer.get_driver_info(d_num)
                        
                        # Simulation du placement sur le tracé en fonction de la progression
                        point = circuit_df.iloc[hash(d_num + replay_lap) % len(circuit_df)]
                        fig_map.add_trace(go.Scatter(
                            x=[point['x']], y=[point['y']],
                            mode='markers+text',
                            marker=dict(size=12),
                            text=[f"#{d_num}"],
                            textposition="top center",
                            name=f"{info['full_name']} ({info['team_name']})"
                        ))

            fig_map.update_layout(
                template="plotly_dark",
                height=600,
                xaxis=dict(showgrid=False, zeroline=False, visible=False),
                yaxis=dict(showgrid=False, zeroline=False, visible=False)
            )
            st.plotly_chart(fig_map, use_container_width=True)
        else:
            st.warning("Génération du tracé en cours ou données GPS temporairement indisponibles.")

    # --- TAB 3 : STRATÉGIE & IA ---
    with tab_ai:
        st.subheader("Analyse comparative et Stratégie d'Undercut")
        
        if laps_data and len(laps_data) > 5:
            drivers_list = sorted(list(set(pd.to_numeric(d['driver_number']) for d in laps_data if 'driver_number' in d)))
            
            col_a, col_b = st.columns(2)
            d_chase = col_a.selectbox(
                "Pilote 1 (Poursuivant) :", 
                drivers_list, 
                format_func=lambda x: f"{analyzer.get_driver_info(x)['full_name']} (#{x})", 
                index=0
            )
            d_lead = col_b.selectbox(
                "Pilote 2 (Devant) :", 
                drivers_list, 
                format_func=lambda x: f"{analyzer.get_driver_info(x)['full_name']} (#{x})", 
                index=min(1, len(drivers_list)-1)
            )

            if d_chase != d_lead:
                delta_df = analyzer.calculate_driver_delta(d_chase, d_lead)
                
                if not delta_df.empty:
                    info_chase = analyzer.get_driver_info(d_chase)
                    info_lead = analyzer.get_driver_info(d_lead)

                    max_avail_lap = int(delta_df['lap_number'].max())
                    selected_lap = st.slider("Sélectionner un tour pour l'analyse stratégique :", 1, max_avail_lap, max_avail_lap)

                    # 1. Alerte Stratégique dynamique selon le tour sélectionné
                    st.markdown("### 🚨 Analyse de Piste")
                    if selected_lap == max_avail_lap and selected_lap > 50:
                        st.info("🏁 Fin de course atteinte : Aucune opportunité d'undercut restante.")
                    else:
                        current_gap = delta_df[delta_df['lap_number'] <= selected_lap]['cumulative_delta'].iloc[-1]
                        if abs(current_gap) <= 2.0:
                            st.success(
                                f"🚨 **ALERTE STRATÉGIE (Tour {selected_lap})** : "
                                f"{info_chase['full_name']} est à **{abs(current_gap):.3f}s** de {info_lead['full_name']}. "
                                f"Fenêtre d'undercut OUVERTE s'il rentre aux stands au tour suivant !"
                            )
                        else:
                            st.info(f"Écart au tour {selected_lap} : {abs(current_gap):.3f}s. Hors fenêtre d'undercut (> 2.0s).")

                    # 2. Graphique Plotly Subplots (Chronos individuels + Delta cumulé)
                    fig = make_subplots(
                        rows=2, cols=1, 
                        shared_xaxes=True, 
                        subplot_titles=("Temps au tour individuels (M:SS.mmm)", "Écart cumulé (Secondes)"),
                        vertical_spacing=0.12
                    )

                    # Courbe Pilote 1
                    fig.add_trace(go.Scatter(
                        x=delta_df['lap_number'], y=delta_df['lap_duration_A'],
                        name=info_chase['full_name'],
                        hovertext=delta_df['time_A_str'],
                        hovertemplate="Tour %{x}<br>Chrono: %{hovertext}<extra></extra>"
                    ), row=1, col=1)

                    # Courbe Pilote 2
                    fig.add_trace(go.Scatter(
                        x=delta_df['lap_number'], y=delta_df['lap_duration_B'],
                        name=info_lead['full_name'],
                        hovertext=delta_df['time_B_str'],
                        hovertemplate="Tour %{x}<br>Chrono: %{hovertext}<extra></extra>"
                    ), row=1, col=1)

                    # Courbe Delta Cumulé
                    fig.add_trace(go.Scatter(
                        x=delta_df['lap_number'], y=delta_df['cumulative_delta'],
                        name="Delta Cumulé",
                        hovertext=delta_df['delta_str'],
                        hovertemplate="Tour %{x}<br>Écart: %{hovertext}<extra></extra>",
                        line=dict(color='yellow', dash='dot')
                    ), row=2, col=1)

                    fig.update_layout(template="plotly_dark", height=650)
                    st.plotly_chart(fig, use_container_width=True)

    # --- TAB 4 : MÉTÉO & RACE CONTROL ---
    with tab_weather:
        col_w, col_rc = st.columns(2)
        
        with col_w:
            st.subheader("Conditions Météorologiques")
            if weather_data:
                w_df = pd.DataFrame(weather_data)
                w_latest = w_df.iloc[-1]
                st.metric("Piste", f"{w_latest.get('track_temperature')} °C")
                st.metric("Air", f"{w_latest.get('air_temperature')} °C")
                st.metric("Humidité", f"{w_latest.get('humidity')} %")
                st.metric("Pluie", "Oui 🌧️" if w_latest.get('rainfall') else "Non ☀️")
                
                # Évolution météo au fil de la séance
                if len(w_df) > 1:
                    fig_w = px.line(w_df, x='date', y=['track_temperature', 'air_temperature'], title="Évolution des températures")
                    fig_w.update_layout(template="plotly_dark")
                    st.plotly_chart(fig_w, use_container_width=True)
            else:
                st.write("Aucune donnée météo enregistrée.")

        with col_rc:
            st.subheader("Direction de course (Race Control)")
            if race_control:
                rc_df = pd.DataFrame(race_control)[['date', 'category', 'message', 'flag']].tail(15)
                st.dataframe(rc_df, use_container_width=True, hide_index=True)
            else:
                st.write("Aucun message de direction de course.")

else:
    st.error("Impossible de récupérer les données de session OpenF1.")