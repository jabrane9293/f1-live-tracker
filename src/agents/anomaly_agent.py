import logging
import pandas as pd
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class AnomalyDetectorAgent:
    """
    Agent IA chargé de détecter les anomalies en piste (crevaisons,
    sorties de piste, trafic important) en analysant les écarts
    soudains sur les temps par secteur.
    """

    def __init__(self, sector_threshold_sec: float = 2.5, z_score_threshold: float = 3.0):
        # Seuil fixe : une perte de +2.5s dans un secteur déclenche une alerte rouge
        self.sector_threshold_sec = sector_threshold_sec
        # Seuil statistique : déviation de 3 écarts-types par rapport au rythme normal
        self.z_score_threshold = z_score_threshold

    def analyze_latest_sector(
        self, 
        driver_number: int, 
        laps_data: List[Dict], 
        sector_name: str = 'duration_sector_1'
    ) -> Optional[str]:
        """
        Analyse le dernier secteur  d'un pilote en le comparant à son historique récent.
        """
        if not laps_data:
            return None

        df = pd.DataFrame(laps_data)
        
        # Sécurisation : on vérifie que la colonne existe et contient des données
        if sector_name not in df.columns:
            return None
            
        driver_df = df[df['driver_number'] == driver_number].dropna(subset=[sector_name])

        if len(driver_df) < 4:
            return None  # Pas assez d'historique pour une base statistique fiable

        # On isole le tout dernier secteur enregistré
        latest_sector = driver_df.iloc[-1][sector_name]
        
        # On calcule le rythme "normal" sur les 8 tours précédents (fenêtre glissante)
        history = driver_df.iloc[:-1][sector_name].tail(8)
        
        mean_sector = history.mean()
        std_sector = history.std()

        # Règle 1 : Anomalie absolue (événement majeur type tête-à-queue ou crevaison)
        time_lost = latest_sector - mean_sector
        if time_lost > self.sector_threshold_sec:
            return (
                f"🔴 INCIDENT DÉTECTÉ : Pilote {driver_number} - Perte de "
                f"{time_lost:.1f}s dans le {sector_name[-1]}. "
                f"Sortie de piste, trafic ou dégât probable."
            )

        # Règle 2 : Anomalie statistique (dégradation anormale ou petite erreur)
        if std_sector > 0:
            z_score = time_lost / std_sector
            if z_score > self.z_score_threshold:
                return (
                    f"🟠 ATTENTION : Pilote {driver_number} - Secteur anormalement lent "
                    f"(Z-Score: +{z_score:.1f}) dans le secteur {sector_name[-1]}."
                )

        return None

    def scan_grid_for_anomalies(self, laps_data: List[Dict]) -> List[str]:
        """
        Scanne l'ensemble des pilotes pour détecter la moindre anomalie 
        sur le dernier secteur validé.
        """
        alerts = []
        if not laps_data:
            return alerts
            
        df = pd.DataFrame(laps_data)
        unique_drivers = df['driver_number'].unique()
        
        sectors = ['duration_sector_1', 'duration_sector_2', 'duration_sector_3']
        
        for driver in unique_drivers:
            for sector in sectors:
                alert = self.analyze_latest_sector(driver, laps_data, sector)
                if alert:
                    alerts.append(alert)
                    
        return alerts

# Test de l'agent
if __name__ == "__main__":
    agent = AnomalyDetectorAgent()
    print("Agent détecteur d'anomalies initialisé.")