import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.ingestion.openf1_client import OpenF1Client
from src.analytics.lap_metrics import LapAnalyzer
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

<<<<<<< HEAD
=======
# --- CACHE DES DONNÉES (Évite les déconnexions API et les rechargements intempestifs) ---
@st.cache_data(ttl=3600)
def get_cached_location(session_key: int, driver_number: int):
    return client.get_location(session_key, driver_number=driver_number)

@st.cache_data(ttl=3600)
def get_cached_laps(session_key: int):
    return client.get_laps(session_key)

@st.cache_data(ttl=86400) # Cache de 24h pour les GP (ils ne changent pas)
def get_cached_meetings(year: int):
    return client.get_meetings(year)

@st.cache_data(ttl=3600)
def get_cached_sessions(meeting_key: int):
    return client.get_sessions(meeting_key)

@st.cache_data(ttl=60) # Rafraîchi toutes les minutes pour le Live
def get_cached_latest_session():
    return client.get_latest_session()

>>>>>>> 1a37a8c451c0e217740e9066942b6b8af9294a7b
# --- SIDEBAR ---
st.sidebar.title("🏎️ Session Control")
mode = st.sidebar.radio("Mode d'analyse :", ["Dernière Session / Live", "Replay Historique"])

if mode == "Dernière Session / Live":
    if st.sidebar.button("🔄 Rafraîchir les données Live"):
        st.cache_data.clear()
        st.rerun()

session_key = None
selected_session_info = None

if mode == "Replay Historique":
    year = st.sidebar.selectbox("Année :", [2026, 2025, 2024, 2023], index=0)
    meetings = get_cached_meetings(year) 
    
    if meetings:
        meeting_options = {}
        for m in meetings:
            clean_name = f"{m.get('country_name', 'GP')} - {m.get('meeting_name', '')}".strip(" -")
            meeting_options[clean_name] = m['meeting_key']
            
        selected_meeting_label = st.sidebar.selectbox("Grand Prix :", list(meeting_options.keys()))
        meeting_key = meeting_options[selected_meeting_label]
        
        sessions = get_cached_sessions(meeting_key) 
        if sessions:
            session_options = {f"{s.get('session_name')} ({s.get('session_type', '')})": s for s in sessions}
            selected_session_label = st.sidebar.selectbox("Séance :", list(session_options.keys()))
            selected_session_info = session_options[selected_session_label]
            session_key = selected_session_info.get("session_key")
else:
    latest = get_cached_latest_session() 
    if latest:
        session_key = latest.get("session_key")
        selected_session_info = latest

# --- CHARGEMENT DE LA SESSION ---
if session_key:
    circuit_name = selected_session_info.get('circuit_short_name') or selected_session_info.get('location') or "Circuit"
    sess_name = selected_session_info.get('session_name') or "Session"
    
    st.title(f"🏎️ {circuit_name} - {sess_name}")

    laps_data = get_cached_laps(session_key)
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
<<<<<<< HEAD
        st.caption("ℹ️ Note : Les données proviennent de la télémétrie brute OpenF1. Les tours annulés (Track Limits) peuvent ne pas être exclus si l'information n'est pas transmise par l'API.")
        
=======
>>>>>>> 1a37a8c451c0e217740e9066942b6b8af9294a7b
        lb_df = analyzer.get_leaderboard()
        if not lb_df.empty:
            st.dataframe(lb_df, use_container_width=True, hide_index=True)
        else:
            st.info("Aucun chrono valide enregistré sur cette session pour le moment.")

        st.subheader("Secteurs Violets (Absolus)")
        purples = analyzer.get_purple_sectors()
        c1, c2, c3 = st.columns(3)
<<<<<<< HEAD
        
        s1 = purples.get("duration_sector_1", {})
        s2 = purples.get("duration_sector_2", {})
        s3 = purples.get("duration_sector_3", {})
        
        c1.metric("Secteur 1", s1.get("time", "-"), s1.get("driver", ""))
        c2.metric("Secteur 2", s2.get("time", "-"), s2.get("driver", ""))
        c3.metric("Secteur 3", s3.get("time", "-"), s3.get("driver", ""))

    # --- TAB 2 : TRACÉ & TÉLÉMÉTRIE 2D (ANIMATION NATIVE) ---
    with tab_telemetry:
        st.subheader("Tracé du circuit et Replay seconde par seconde")
        st.caption("Sélectionnez quelques pilotes pour ne pas surcharger l'animation, puis utilisez le bouton Play du graphique.")
        
        if laps_data:
            unique_drivers = sorted(list(set(pd.to_numeric(d['driver_number']) for d in laps_data if 'driver_number' in d)))
            
            # Sélection des pilotes pour l'animation (limité par défaut pour la fluidité)
            selected_anim_drivers = st.multiselect(
                "Pilotes à suivre en piste :", 
                unique_drivers, 
                default=unique_drivers[:3],
                format_func=lambda x: f"{analyzer.get_driver_info(x)['full_name']} (#{x})"
            )

            if selected_anim_drivers:
                with st.spinner("Téléchargement de la télémétrie GPS (peut prendre quelques secondes)..."):
                    # 1. Dessin du tracé de base propre (Leader)
                    circuit_locs = client.get_location(session_key, driver_number=unique_drivers[0])
                    if circuit_locs:
                        circuit_df = pd.DataFrame(circuit_locs)
                        # TRI CRUCIAL pour éviter le "gribouillis"
                        circuit_df['date_dt'] = pd.to_datetime(circuit_df['date'], format='ISO8601')
                        circuit_df = circuit_df.sort_values('date_dt').iloc[::5]
                        

                        # 2. Récupération des positions pour les pilotes sélectionnés
                        all_frames = []
                        for d in selected_anim_drivers:
                            d_locs = client.get_location(session_key, driver_number=d)
                            if d_locs:
                                d_df = pd.DataFrame(d_locs)
                                d_df = d_df.sort_values('date')
                                # Arrondi à la seconde pour regrouper les frames
                                d_df['time_sec'] = pd.to_datetime(d_df['date'], format='ISO8601').dt.round('s').dt.strftime('%H:%M:%S')
                                d_df['driver_name'] = analyzer.get_driver_info(d)['full_name']
                                # On garde une position par seconde
                                d_df = d_df.drop_duplicates(subset=['time_sec'])
=======

        # Fonction de sécurité pour extraire les secteurs
        def extract_sector_info(sec_data):
            if isinstance(sec_data, dict):
                return sec_data.get("time", "-"), sec_data.get("driver", "")
            elif isinstance(sec_data, str):
                return sec_data, ""
            return "-", ""

        s1_time, s1_driver = extract_sector_info(purples.get("duration_sector_1"))
        s2_time, s2_driver = extract_sector_info(purples.get("duration_sector_2"))
        s3_time, s3_driver = extract_sector_info(purples.get("duration_sector_3"))

        c1.metric("Secteur 1", s1_time, s1_driver)
        c2.metric("Secteur 2", s2_time, s2_driver)
        c3.metric("Secteur 3", s3_time, s3_driver)

    # --- TAB 2 : TRACÉ & TÉLÉMÉTRIE 2D (COMPLET) ---
    with tab_telemetry:
        st.subheader("Tracé du circuit et Replay complet du tour")
        
        if laps_data:
            laps_df = pd.DataFrame(laps_data)
            unique_drivers = sorted(list(set(pd.to_numeric(laps_df['driver_number']))))
            max_laps = int(laps_df['lap_number'].max())

            col_lap, col_drv = st.columns([1, 2])
            
            selected_replay_lap = col_lap.number_input(
                "Tour à rejouer :", 
                min_value=1, 
                max_value=max_laps, 
                value=1,
                key="telemetry_lap_input"
            )

            # Fixation des pilotes dans l'état de session
            if "telemetry_drivers" not in st.session_state:
                st.session_state.telemetry_drivers = unique_drivers[:3]

            selected_anim_drivers = col_drv.multiselect(
                "Pilotes à suivre en piste :", 
                unique_drivers, 
                key="telemetry_drivers",
                format_func=lambda x: f"{analyzer.get_driver_info(x)['full_name']} (#{x})"
            )

            if selected_anim_drivers:
                with st.spinner("Génération de la télémétrie du tour (boucle complète)..."):
                    circuit_locs = get_cached_location(session_key, driver_number=unique_drivers[0])
                    if circuit_locs:
                        circuit_df = pd.DataFrame(circuit_locs)
                        circuit_df['date_dt'] = pd.to_datetime(circuit_df['date'], format='ISO8601')
                        circuit_df = circuit_df.sort_values('date_dt').iloc[::5]

                        lap_time_bounds = laps_df[laps_df['lap_number'] == selected_replay_lap]
                        all_frames = []

                        for d in selected_anim_drivers:
                            d_locs = get_cached_location(session_key, driver_number=d)
                            if d_locs:
                                d_df = pd.DataFrame(d_locs)
                                d_df['date_dt'] = pd.to_datetime(d_df['date'], format='ISO8601')
                                d_df = d_df.sort_values('date_dt')

                                d_laps = lap_time_bounds[lap_time_bounds['driver_number'] == d]
                                if not d_laps.empty and 'date_start' in d_laps.columns:
                                    t_start = pd.to_datetime(d_laps.iloc[0]['date_start'], format='ISO8601')
                                    lap_dur = d_laps.iloc[0].get('lap_duration')
                                    
                                    # Cadrage sur toute la durée du tour
                                    if pd.notna(lap_dur):
                                        t_end = t_start + pd.Timedelta(seconds=lap_dur)
                                        d_df = d_df[(d_df['date_dt'] >= t_start) & (d_df['date_dt'] <= t_end)]
                                    else:
                                        d_df = d_df[d_df['date_dt'] >= t_start].iloc[:350]

                                # Sous-échantillonnage pour fluidité Plotly
                                if len(d_df) > 80:
                                    step = len(d_df) // 80
                                    d_df = d_df.iloc[::step]
                                    
                                d_df['step'] = range(len(d_df))
                                d_df['driver_name'] = analyzer.get_driver_info(d)['full_name']
>>>>>>> 1a37a8c451c0e217740e9066942b6b8af9294a7b
                                all_frames.append(d_df)

                        if all_frames:
                            anim_df = pd.concat(all_frames)
<<<<<<< HEAD
                            anim_df = anim_df.sort_values('time_sec')

                            # Graphique Plotly Animé
                            fig_anim = px.scatter(
                                anim_df, x='x', y='y', color='driver_name',
                                animation_frame='time_sec',
                                hover_name='driver_name'
                            )
                            
                            # Ajout du tracé fixe en arrière-plan
                            fig_anim.add_trace(go.Scatter(
                                x=circuit_df['x'], y=circuit_df['y'],
                                mode='lines', line=dict(color='gray', width=2),
                                name='Piste', hoverinfo='skip', opacity=0.5
                            ))

                            fig_anim.update_layout(
                                template="plotly_dark",
                                height=700,
                                xaxis=dict(showgrid=False, zeroline=False, visible=False),
                                yaxis=dict(showgrid=False, zeroline=False, visible=False),
                                updatemenus=[dict(type="buttons", buttons=[dict(label="▶️ Play", method="animate", args=[None])])]
                            )
                            
                            # Ajustement de la vitesse de l'animation
                            fig_anim.layout.updatemenus[0].buttons[0].args[1]['frame']['duration'] = 200
                            
                            st.plotly_chart(fig_anim, use_container_width=True)
                        else:
                            st.warning("Données GPS introuvables pour ces pilotes.")
=======
                            fig_anim = px.scatter(
                                anim_df, x='x', y='y', color='driver_name',
                                animation_frame='step', hover_name='driver_name'
                            )
                            
                            fig_anim.add_trace(go.Scatter(
                                x=circuit_df['x'], y=circuit_df['y'],
                                mode='lines', line=dict(color='gray', width=2),
                                name='Piste', hoverinfo='skip', opacity=0.4
                            ))

                            fig_anim.update_layout(
                                template="plotly_dark", height=650,
                                xaxis=dict(showgrid=False, zeroline=False, visible=False),
                                yaxis=dict(showgrid=False, zeroline=False, visible=False)
                            )
                            
                            if getattr(fig_anim.layout, 'updatemenus', None):
                                fig_anim.layout.updatemenus[0].buttons[0].args[1]['frame']['duration'] = 200
                                fig_anim.layout.updatemenus[0].buttons[0].args[1]['transition']['duration'] = 100
                            
                            st.plotly_chart(fig_anim, use_container_width=True)
                        else:
                            st.warning("Télémétrie GPS incomplète pour ce tour.")
>>>>>>> 1a37a8c451c0e217740e9066942b6b8af9294a7b
                    else:
                        st.warning("Impossible de générer le tracé du circuit.")

    # --- TAB 3 : STRATÉGIE & IA ---
    with tab_ai:
        st.subheader("Analyse comparative et Stratégie d'Undercut")
        if laps_data and len(laps_data) > 5:
            drivers_list = sorted(list(set(pd.to_numeric(d['driver_number']) for d in laps_data if 'driver_number' in d)))
            
            col_a, col_b = st.columns(2)
            d_chase = col_a.selectbox(
                "Pilote 1 (Poursuivant) :", drivers_list, 
                format_func=lambda x: f"{analyzer.get_driver_info(x)['full_name']} (#{x})", 
                index=0, key="strat_chase"
            )
            d_lead = col_b.selectbox(
                "Pilote 2 (Devant) :", drivers_list, 
                format_func=lambda x: f"{analyzer.get_driver_info(x)['full_name']} (#{x})", 
                index=min(1, len(drivers_list)-1), key="strat_lead"
            )

            if d_chase != d_lead:
                delta_df = analyzer.calculate_driver_delta(d_chase, d_lead)
                if not delta_df.empty:
                    info_chase = analyzer.get_driver_info(d_chase)
                    info_lead = analyzer.get_driver_info(d_lead)
                    max_avail_lap = int(delta_df['lap_number'].max())
                    
                    selected_lap = st.slider(
                        "Tour d'analyse stratégique :", 
                        min_value=1, max_value=max_avail_lap, value=1, key="strat_slider"
                    )

<<<<<<< HEAD
                    st.markdown("### 🚨 Analyse de Piste")
=======
>>>>>>> 1a37a8c451c0e217740e9066942b6b8af9294a7b
                    current_gap = delta_df[delta_df['lap_number'] <= selected_lap]['cumulative_delta'].iloc[-1]
                    
                    if abs(current_gap) <= 2.0:
                        st.success(
                            f"🚨 **ALERTE STRATÉGIE (Tour {selected_lap})** : "
                            f"{info_chase['full_name']} est à **{abs(current_gap):.3f}s** de {info_lead['full_name']}. "
                            f"Fenêtre d'undercut OUVERTE s'il boxe !"
                        )
                    else:
                        st.info(f"Écart au tour {selected_lap} : {abs(current_gap):.3f}s. Hors fenêtre d'undercut (> 2.0s).")

                    fig = make_subplots(
                        rows=2, cols=1, shared_xaxes=True, 
                        subplot_titles=("Temps au tour individuels (M:SS.mmm)", "Écart cumulé (Secondes)"),
                        vertical_spacing=0.12
                    )

                    fig.add_trace(go.Scatter(
                        x=delta_df['lap_number'], y=delta_df['lap_duration_A'],
                        name=info_chase['full_name'], hovertext=delta_df['time_A_str'],
                        hovertemplate="Tour %{x}<br>Chrono: %{hovertext}<extra></extra>"
                    ), row=1, col=1)

                    fig.add_trace(go.Scatter(
                        x=delta_df['lap_number'], y=delta_df['lap_duration_B'],
                        name=info_lead['full_name'], hovertext=delta_df['time_B_str'],
                        hovertemplate="Tour %{x}<br>Chrono: %{hovertext}<extra></extra>"
                    ), row=1, col=1)

                    fig.add_trace(go.Scatter(
                        x=delta_df['lap_number'], y=delta_df['cumulative_delta'],
                        name="Delta Cumulé", hovertext=delta_df['delta_str'],
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
    st.error("Impossible de récupérer les données de session OpenF1. En attente du début de séance...")