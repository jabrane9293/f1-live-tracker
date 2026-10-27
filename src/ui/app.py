import streamlit as st
import pandas as pd
import plotly.express as px
import threading
import asyncio
import time

# Import de nos modules métiers
from src.ingestion.stream_manager import StreamManager
from src.analytics.lap_metrics import LapAnalyzer
from src.models.lap_predictor import LapPredictor
from src.agents.strategist_agent import StrategistAgent
from src.agents.anomaly_agent import AnomalyDetectorAgent

# 1. Configuration de la page (Optimisé Mobile/Desktop)
st.set_page_config(
    page_title="F1 Live Tracker & AI Strategy",
    page_icon="🏎️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Initialisation des composants Backend en Cache (Singleton)
@st.cache_resource
def init_backend():
    """Initialise les agents et le gestionnaire de flux une seule fois."""
    manager = StreamManager(poll_interval=5)
    
    # Lancement du StreamManager asynchrone dans un thread séparé
    def run_async_loop():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(manager.start())
        loop.run_forever()
        
    thread = threading.Thread(target=run_async_loop, daemon=True)
    thread.start()
    
    # Attendre quelques secondes que le premier run récupère les données
    time.sleep(3)
    
    return {
        "stream_manager": manager,
        "predictor": LapPredictor(),
        "strategist": StrategistAgent(pit_stop_loss_sec=22.0),
        "anomaly_detector": AnomalyDetectorAgent()
    }

backend = init_backend()
manager = backend["stream_manager"]
predictor = backend["predictor"]
strategist = backend["strategist"]
anomaly_detector = backend["anomaly_detector"]

# 3. Récupération des données en temps réel
laps_data = manager.get_latest_laps()
session_info = manager.get_session_info()

# Entraînement du modèle ML à la volée
if laps_data:
    predictor.train(laps_data)

# 4. Interface Utilisateur (UI)
st.title("🏎️ F1 Live Tracker & AI Strategist")

if session_info:
    st.caption(f"Session en cours : {session_info.get('meeting_name')} - {session_info.get('session_name')}")
else:
    st.warning("Aucune session active détectée sur l'API OpenF1 pour le moment.")

# Utilisation des onglets (Idéal pour l'iPhone 11 Pro)
tab1, tab2, tab3 = st.tabs(["📊 Leaderboard", "🤖 Alertes IA (Race Control)", "📈 Stratégie & Deltas"])

if not laps_data:
    st.info("En attente des données de télémétrie... L'API se charge.")
else:
    analyzer = LapAnalyzer(laps_data)

    # --- ONGLET 1 : LEADERBOARD ---
    with tab1:
        st.subheader("Meilleurs temps au tour absolus")
        best_laps = analyzer.get_best_laps()
        if not best_laps.empty:
            # Formatage pour un affichage propre
            st.dataframe(
                best_laps.style.format({"lap_duration": "{:.3f} s"}),
                use_container_width=True,
                hide_index=True
            )
        
        st.subheader("Secteurs Violets (Meilleurs absolus)")
        purple = analyzer.get_purple_sectors()
        cols = st.columns(3)
        cols[0].metric("Secteur 1", f"{purple.get('duration_sector_1', 0):.3f}s")
        cols[1].metric("Secteur 2", f"{purple.get('duration_sector_2', 0):.3f}s")
        cols[2].metric("Secteur 3", f"{purple.get('duration_sector_3', 0):.3f}s")

    # --- ONGLET 2 : ALERTES IA ---
    with tab2:
        st.subheader("Race Control & Anomalies en piste")
        # 1. Anomalies
        anomalies = anomaly_detector.scan_grid_for_anomalies(laps_data)
        if anomalies:
            for alert in anomalies:
                if "INCIDENT" in alert:
                    st.error(alert, icon="🔴")
                else:
                    st.warning(alert, icon="🟠")
        else:
            st.success("🟢 Piste claire. Aucune anomalie détectée.")

        st.markdown("---")
        
        st.subheader("Ingénieur de Piste (Prédictions)")
        # Sélection d'un pilote pour voir sa prédiction (ex: 1 pour Verstappen, 16 pour Leclerc)
        unique_drivers = sorted(list(set(d['driver_number'] for d in laps_data if 'driver_number' in d)))
        selected_driver = st.selectbox("Sélectionnez un pilote pour analyser son prochain tour :", unique_drivers)
        
        if selected_driver:
            pred = predictor.predict_next_lap(laps_data, selected_driver)
            cliff_alert = strategist.detect_tire_cliff(selected_driver, predictor, laps_data)
            
            if pred:
                st.metric(f"Prédiction prochain tour (Pilote {selected_driver})", f"{pred:.3f} s")
            if cliff_alert:
                st.warning(cliff_alert, icon="⚠️")
            else:
                st.info("Pneumatiques dans la fenêtre de fonctionnement optimale.")

    # --- ONGLET 3 : STRATÉGIE ET DELTAS ---
    with tab3:
        st.subheader("Analyse d'Undercut en temps réel")
        col_chaser, col_leader = st.columns(2)
        driver_chasing = col_chaser.selectbox("Pilote Poursuivant (ex: 16)", unique_drivers, index=0)
        driver_leading = col_leader.selectbox("Pilote Devant (ex: 1)", unique_drivers, index=min(1, len(unique_drivers)-1))

        if driver_chasing != driver_leading:
            # Calcul du delta
            delta_df = analyzer.calculate_driver_delta(driver_chasing, driver_leading)
            
            if not delta_df.empty:
                # Alerte Stratégique
                undercut_alert = strategist.analyze_undercut_opportunity(driver_chasing, driver_leading, delta_df)
                if undercut_alert:
                    st.success(undercut_alert, icon="🚨")
                
                # Graphique Plotly Responsive
                fig = px.line(
                    delta_df, 
                    x='lap_number', 
                    y='cumulative_delta',
                    title=f"Écart cumulé en secondes : Pilote {driver_chasing} vs Pilote {driver_leading}",
                    labels={'lap_number': 'Numéro du Tour', 'cumulative_delta': 'Écart (secondes)'},
                    markers=True
                )
                # Ligne zéro pour repère visuel
                fig.add_hline(y=0, line_dash="dash", line_color="white", opacity=0.5)
                # Inverser l'axe Y (plus le delta est négatif, plus le poursuivant rattrape)
                fig.update_yaxes(autorange="reversed")
                
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Pas assez de tours en commun pour calculer le delta.")

# Bouton de rafraîchissement manuel pour l'UI (le backend tourne déjà tout seul)
st.sidebar.button("🔄 Rafraîchir les données")
st.sidebar.markdown("---")
st.sidebar.caption("Déployé via GitHub Actions sur Google Cloud Run.")