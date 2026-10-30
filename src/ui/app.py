import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time

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

# --- CACHE DES DONNÉES ---
@st.cache_data(ttl=3600)
def get_cached_location(session_key: int, driver_number: int):
    return client.get_location(session_key, driver_number=driver_number)

@st.cache_data(ttl=30) # 30s pour les chronos en Live
def get_cached_laps(session_key: int):
    return client.get_laps(session_key)

@st.cache_data(ttl=86400)
def get_cached_meetings(year: int):
    return client.get_meetings(year)

@st.cache_data(ttl=3600)
def get_cached_sessions(meeting_key: int):
    return client.get_sessions(meeting_key)

@st.cache_data(ttl=30)
def get_cached_latest_session():
    return client.get_latest_session()

@st.cache_data(ttl=30)
def get_cached_stints(session_key: int):
    return client.get_stints(session_key)

@st.cache_data(ttl=30)
def get_cached_intervals(session_key: int):
    return client.get_intervals(session_key)

@st.cache_data(ttl=60)
def get_cached_radio(session_key: int):
    return client.get_team_radio(session_key)

@st.cache_data(ttl=300) 
def get_cached_car_data(session_key: int, driver_number: int):
    return client.get_car_data(session_key, driver_number=driver_number)


# --- SIDEBAR & GESTION DU LIVE ---
st.sidebar.title("🏎️ Session Control")
mode = st.sidebar.radio("Mode d'analyse :", ["Dernière Session / Live", "Replay Historique"])

auto_refresh = False
if mode == "Dernière Session / Live":
    st.sidebar.markdown("---")
    auto_refresh = st.sidebar.toggle("⏱️ Activer Auto-Refresh (15s)")
    if st.sidebar.button("🔄 Rafraîchir manuellement"):
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
    if auto_refresh:
        st.caption("🔴 DIRECT - Actualisation automatique activée.")

    laps_data = get_cached_laps(session_key)
    drivers_data = client.get_drivers(session_key)
    weather_data = client.get_weather(session_key)
    race_control = client.get_race_control(session_key)
    stints_data = get_cached_stints(session_key)
    intervals_data = get_cached_intervals(session_key)

    analyzer = LapAnalyzer(laps_data, drivers_data)

    tab_lb, tab_telemetry, tab_ai, tab_advanced, tab_radio, tab_weather = st.tabs([
        "📊 Leaderboard & Pneus", 
        "🗺️ Tracé 2D Animé", 
        "🤖 Stratégie & IA",
        "📈 Télémétrie Pédales",
        "📻 Team Radio",
        "🚩 Météo & Race Control"
    ])

    # --- TAB 1 : LEADERBOARD, STINTS & INTERVALS ---
    with tab_lb:
        st.subheader("Classement, Écarts et Gommes")
        lb_df = analyzer.get_leaderboard()
        
        if not lb_df.empty:
            # Ajout des Pneus
            if stints_data:
                stints_df = pd.DataFrame(stints_data)
                last_stints = stints_df.sort_values('stint_number').groupby('driver_number').tail(1)
                last_stints['Pneus'] = last_stints['compound'] + " (" + last_stints['tyre_age_at_start'].astype(str) + " trs)"
                lb_df = pd.merge(lb_df, last_stints[['driver_number', 'Pneus']], on='driver_number', how='left')
                lb_df['Pneus'] = lb_df['Pneus'].fillna("Inconnu")
            else:
                lb_df['Pneus'] = "N/A"

            # Ajout des Gaps (Écarts)
            if intervals_data:
                int_df = pd.DataFrame(intervals_data)
                last_intervals = int_df.sort_values('date').groupby('driver_number').tail(1)
                lb_df = pd.merge(lb_df, last_intervals[['driver_number', 'gap_to_leader', 'interval']], on='driver_number', how='left')
                lb_df['Écart Leader'] = lb_df['gap_to_leader'].apply(lambda x: f"+{x}s" if pd.notna(x) else "-")
                lb_df['Intervalle'] = lb_df['interval'].apply(lambda x: f"+{x}s" if pd.notna(x) else "-")
            else:
                lb_df['Écart Leader'] = "-"
                lb_df['Intervalle'] = "-"

            display_cols = ['Position', 'driver_number', 'full_name', 'team_name', 'Écart Leader', 'Intervalle', 'Pneus', 'Temps au tour', 'Secteur 1', 'Secteur 2', 'Secteur 3', 'lap_number']
            st.dataframe(lb_df[[c for c in display_cols if c in lb_df.columns]], use_container_width=True, hide_index=True)
        else:
            st.info("Aucun chrono valide enregistré sur cette session pour le moment.")

        st.subheader("Secteurs Violets (Absolus)")
        purples = analyzer.get_purple_sectors()
        c1, c2, c3 = st.columns(3)

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

    # --- TAB 2 : TRACÉ & TÉLÉMÉTRIE 2D ANIMÉ ---
    with tab_telemetry:
        st.subheader("Tracé du circuit et Replay complet du tour")
        
        if laps_data:
            laps_df = pd.DataFrame(laps_data)
            laps_df['driver_number'] = pd.to_numeric(laps_df['driver_number'], errors='coerce').fillna(0).astype(int)
            laps_df = laps_df[laps_df['driver_number'] > 0]
            
            unique_drivers = sorted(list(set(laps_df['driver_number'])))
            max_laps = int(laps_df['lap_number'].max())

            col_lap, col_drv = st.columns([1, 2])
            selected_replay_lap = col_lap.number_input("Tour à rejouer :", min_value=1, max_value=max_laps, value=1, key="telemetry_lap_input")

            if "telemetry_drivers" not in st.session_state:
                st.session_state.telemetry_drivers = unique_drivers[:3]

            selected_anim_drivers = col_drv.multiselect("Pilotes à suivre en piste :", unique_drivers, key="telemetry_drivers", format_func=lambda x: f"{analyzer.get_driver_info(x)['full_name']} (#{x})")

            if selected_anim_drivers:
                with st.spinner("Génération de l'animation..."):
                    circuit_locs = []
                    for fallback_driver in unique_drivers:
                        locs = get_cached_location(session_key, driver_number=fallback_driver)
                        if locs and len(locs) > 50:
                            circuit_locs = locs
                            break 

                    if circuit_locs:
                        circuit_df = pd.DataFrame(circuit_locs)
                        circuit_df['date_dt'] = pd.to_datetime(circuit_df['date'], format='ISO8601', utc=True)
                        circuit_df = circuit_df.sort_values('date_dt').iloc[::5]

                        lap_time_bounds = laps_df[laps_df['lap_number'] == selected_replay_lap]
                        all_frames = []
                        FRAME_COUNT = 100

                        for d in selected_anim_drivers:
                            d_locs = get_cached_location(session_key, driver_number=d)
                            if d_locs:
                                d_df = pd.DataFrame(d_locs)
                                d_df['date_dt'] = pd.to_datetime(d_df['date'], format='ISO8601', utc=True)
                                d_df = d_df.sort_values('date_dt')

                                d_laps = lap_time_bounds[lap_time_bounds['driver_number'] == d]
                                if not d_laps.empty and 'date_start' in d_laps.columns:
                                    t_start = pd.to_datetime(d_laps.iloc[0]['date_start'], format='ISO8601', utc=True)
                                    lap_dur = d_laps.iloc[0].get('lap_duration')
                                    
                                    if pd.notna(lap_dur):
                                        t_end = t_start + pd.Timedelta(seconds=lap_dur)
                                        d_df = d_df[(d_df['date_dt'] >= t_start) & (d_df['date_dt'] <= t_end)]
                                    else:
                                        d_df = d_df[d_df['date_dt'] >= t_start].iloc[:350]

                                    if len(d_df) > 0:
                                        indices = [int(i * len(d_df) / FRAME_COUNT) for i in range(FRAME_COUNT)]
                                        d_df = d_df.iloc[indices].copy()
                                        d_df['step'] = range(FRAME_COUNT)
                                        d_df['driver_name'] = analyzer.get_driver_info(d)['full_name']
                                        all_frames.append(d_df)

                        if all_frames:
                            anim_df = pd.concat(all_frames)
                            fig_anim = px.scatter(anim_df, x='x', y='y', color='driver_name', animation_frame='step', hover_name='driver_name')
                            fig_anim.update_traces(marker=dict(size=14, line=dict(width=2, color='white')), selector=dict(mode='markers'))
                            fig_anim.add_trace(go.Scatter(x=circuit_df['x'], y=circuit_df['y'], mode='lines', line=dict(color='gray', width=3), name='Piste', hoverinfo='skip', opacity=0.4))
                            fig_anim.update_layout(template="plotly_dark", height=650, xaxis=dict(showgrid=False, zeroline=False, visible=False), yaxis=dict(showgrid=False, zeroline=False, visible=False))
                            if getattr(fig_anim.layout, 'updatemenus', None):
                                fig_anim.layout.updatemenus[0].buttons[0].args[1]['frame']['duration'] = 150
                                fig_anim.layout.updatemenus[0].buttons[0].args[1]['transition']['duration'] = 50
                            st.plotly_chart(fig_anim, use_container_width=True)
                        else:
                            st.warning("Télémétrie GPS incomplète pour ce tour.")
                    else:
                        st.warning("Impossible de générer le tracé du circuit.")

    # --- TAB 3 : STRATÉGIE & IA ---
    with tab_ai:
        st.subheader("Analyse comparative et Stratégie d'Undercut")
        if laps_data and len(laps_data) > 5:
            drivers_list = sorted(list(set(pd.to_numeric(d['driver_number']) for d in laps_data if 'driver_number' in d)))
            col_a, col_b = st.columns(2)
            d_chase = col_a.selectbox("Pilote 1 (Poursuivant) :", drivers_list, format_func=lambda x: f"{analyzer.get_driver_info(x)['full_name']} (#{x})", index=0, key="strat_chase")
            d_lead = col_b.selectbox("Pilote 2 (Devant) :", drivers_list, format_func=lambda x: f"{analyzer.get_driver_info(x)['full_name']} (#{x})", index=min(1, len(drivers_list)-1), key="strat_lead")

            if d_chase != d_lead:
                delta_df = analyzer.calculate_driver_delta(d_chase, d_lead)
                if not delta_df.empty:
                    info_chase = analyzer.get_driver_info(d_chase)
                    info_lead = analyzer.get_driver_info(d_lead)
                    max_avail_lap = int(delta_df['lap_number'].max())
                    selected_lap = st.slider("Tour d'analyse stratégique :", min_value=1, max_value=max_avail_lap, value=1, key="strat_slider")
                    current_gap = delta_df[delta_df['lap_number'] <= selected_lap]['cumulative_delta'].iloc[-1]
                    
                    if abs(current_gap) <= 2.0:
                        st.success(f"🚨 **ALERTE STRATÉGIE (Tour {selected_lap})** : {info_chase['full_name']} est à **{abs(current_gap):.3f}s** de {info_lead['full_name']}. Fenêtre d'undercut OUVERTE s'il boxe !")
                    else:
                        st.info(f"Écart au tour {selected_lap} : {abs(current_gap):.3f}s. Hors fenêtre d'undercut (> 2.0s).")

                    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, subplot_titles=("Temps au tour individuels (M:SS.mmm)", "Écart cumulé (Secondes)"), vertical_spacing=0.12)
                    fig.add_trace(go.Scatter(x=delta_df['lap_number'], y=delta_df['lap_duration_A'], name=info_chase['full_name'], hovertext=delta_df['time_A_str'], hovertemplate="Tour %{x}<br>Chrono: %{hovertext}<extra></extra>"), row=1, col=1)
                    fig.add_trace(go.Scatter(x=delta_df['lap_number'], y=delta_df['lap_duration_B'], name=info_lead['full_name'], hovertext=delta_df['time_B_str'], hovertemplate="Tour %{x}<br>Chrono: %{hovertext}<extra></extra>"), row=1, col=1)
                    fig.add_trace(go.Scatter(x=delta_df['lap_number'], y=delta_df['cumulative_delta'], name="Delta Cumulé", hovertext=delta_df['delta_str'], hovertemplate="Tour %{x}<br>Écart: %{hovertext}<extra></extra>", line=dict(color='yellow', dash='dot')), row=2, col=1)
                    fig.update_layout(template="plotly_dark", height=650)
                    st.plotly_chart(fig, use_container_width=True)

    # --- TAB 4 : TÉLÉMÉTRIE AVANCÉE (PÉDALES/VITESSE) ---
    with tab_advanced:
        st.subheader("Télémétrie brute (Accélération, Frein, Vitesse, Rapports)")
        st.caption("Données échantillonnées à 3.7Hz.")
        
        if laps_data:
            unique_drivers = sorted(list(set(pd.to_numeric(pd.DataFrame(laps_data)['driver_number']))))
            c_drv, c_lap = st.columns(2)
            sel_drv = c_drv.selectbox("Pilote (Télémétrie) :", unique_drivers, format_func=lambda x: f"{analyzer.get_driver_info(x)['full_name']} (#{x})", key="adv_drv")
            
            driver_laps = pd.DataFrame(laps_data)
            driver_laps = driver_laps[driver_laps['driver_number'] == sel_drv].dropna(subset=['lap_duration'])
            
            if not driver_laps.empty:
                sel_lap = c_lap.selectbox("Tour d'analyse :", sorted(driver_laps['lap_number'].unique(), reverse=True), key="adv_lap")
                
                with st.spinner("Téléchargement de la télémétrie haute fréquence..."):
                    car_data = get_cached_car_data(session_key, sel_drv)
                    if car_data:
                        cd_df = pd.DataFrame(car_data)
                        cd_df['date_dt'] = pd.to_datetime(cd_df['date'], format='ISO8601', utc=True)
                        
                        lap_info = driver_laps[driver_laps['lap_number'] == sel_lap].iloc[0]
                        t_start = pd.to_datetime(lap_info['date_start'], format='ISO8601', utc=True)
                        t_end = t_start + pd.Timedelta(seconds=lap_info['lap_duration'])
                        
                        tour_df = cd_df[(cd_df['date_dt'] >= t_start) & (cd_df['date_dt'] <= t_end)]
                        
                        if not tour_df.empty:
                            fig_adv = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.05, subplot_titles=("Vitesse (km/h)", "Pédales : Gaz (%) & Frein (%)", "Rapport de boîte (Gear)"))
                            fig_adv.add_trace(go.Scatter(x=tour_df['date_dt'], y=tour_df['speed'], name="Vitesse", line=dict(color="cyan")), row=1, col=1)
                            fig_adv.add_trace(go.Scatter(x=tour_df['date_dt'], y=tour_df['throttle'], name="Gaz", line=dict(color="green")), row=2, col=1)
                            fig_adv.add_trace(go.Scatter(x=tour_df['date_dt'], y=tour_df['brake'], name="Frein", line=dict(color="red")), row=2, col=1)
                            fig_adv.add_trace(go.Scatter(x=tour_df['date_dt'], y=tour_df['n_gear'], name="Gear", mode="lines+markers", line=dict(color="orange")), row=3, col=1)
                            fig_adv.update_layout(template="plotly_dark", height=800, hovermode="x unified")
                            st.plotly_chart(fig_adv, use_container_width=True)
                        else:
                            st.warning("Données non disponibles pour ce tour précis.")
                    else:
                        st.warning("Télémétrie indisponible pour ce pilote.")

    # --- TAB 5 : TEAM RADIO ---
    with tab_radio:
        st.subheader("📻 Communications Team Radio")
        radios = get_cached_radio(session_key)
        
        if radios:
            radio_df = pd.DataFrame(radios)
            radio_df['date_dt'] = pd.to_datetime(radio_df['date'], format='ISO8601', utc=True)
            radio_df = radio_df.sort_values('date_dt', ascending=False).head(20)
            
            st.write(f"Derniers messages captés ({len(radio_df)} affichés) :")
            for _, r in radio_df.iterrows():
                d_info = analyzer.get_driver_info(r['driver_number'])
                col_info, col_audio = st.columns([1, 2])
                col_info.markdown(f"**{d_info['full_name']}** ({d_info['team_name']})<br/>*{r['date_dt'].strftime('%H:%M:%S')}*", unsafe_allow_html=True)
                col_audio.audio(r['recording_url'])
                st.divider()
        else:
            st.info("Aucun message radio hébergé par l'API pour cette session.")

    # --- TAB 6 : MÉTÉO & RACE CONTROL ---
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

    # --- BOUCLE D'AUTO-REFRESH NATIVE ---
    if auto_refresh:
        time.sleep(15)
        st.cache_data.clear()
        st.rerun()

else:
    st.error("En attente du début de la séance...")
    if auto_refresh:
        time.sleep(15)
        st.rerun()