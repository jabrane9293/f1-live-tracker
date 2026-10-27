import logging
import pandas as pd
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class StrategistAgent:
    """
    Agent IA qui analyse le flux de course pour détecter les opportunités
    stratégiques (undercut, dégradation anormale) et générer des alertes textuelles.
    """

    def __init__(self, pit_stop_loss_sec: float = 22.0):
        # Le temps perdu moyen pour un arrêt aux stands (dépend du circuit)
        self.pit_stop_loss_sec = pit_stop_loss_sec
        
        # Seuil d'écart pour considérer un undercut possible
        self.undercut_window_sec = 2.0 
        
        # Seuil de chute de rythme pour alerter sur la dégradation
        self.cliff_drop_sec = 1.5 

    def analyze_undercut_opportunity(
        self, 
        driver_chasing: int, 
        driver_leading: int, 
        delta_df: pd.DataFrame
    ) -> Optional[str]:
        """
        Analyse si le pilote derrière (chasing) est dans une fenêtre pour 
        dépasser par les stands (undercut) le pilote devant (leading).
        """
        if delta_df.empty or 'cumulative_delta' not in delta_df.columns:
            return None

        # On regarde le delta actuel sur le dernier tour disponible
        latest_gap = delta_df['cumulative_delta'].iloc[-1]
        
        # Si le poursuivant est à plus de 5 secondes, l'undercut est impossible
        if abs(latest_gap) > 5.0:
            return None

        # Si le poursuivant est dans la fenêtre (ex: < 2.0s), il peut tenter
        if abs(latest_gap) <= self.undercut_window_sec:
            return (
                f"🚨 ALERTE STRATÉGIE : Le pilote {driver_chasing} est à {abs(latest_gap):.1f}s "
                f"du pilote {driver_leading}. Fenêtre d'undercut OUVERTE. "
                f"S'il boxe ce tour, il ressortira devant si l'arrêt est rapide."
            )
            
        return None

    def detect_tire_cliff(self, driver_number: int, predictor_model, laps_data: List[Dict]) -> Optional[str]:
        """
        Utilise le modèle de prédiction pour détecter si le pneu s'effondre (cliff).
        """
        if not laps_data:
            return None

        df_raw = pd.DataFrame(laps_data)
        driver_df = df_raw[df_raw['driver_number'] == driver_number]
        
        if len(driver_df) < 5:
            return None # Pas assez d'historique sur ce relais

        # Moyenne des chronos récents (rythme normal)
        recent_pace = driver_df['lap_duration'].tail(3).mean()
        
        # Prédiction du prochain tour par le modèle ML
        next_lap_pred = predictor_model.predict_next_lap(laps_data, driver_number)
        
        if next_lap_pred:
            # Si le modèle prédit un temps significativement plus lent que le rythme récent
            drop = next_lap_pred - recent_pace
            if drop > self.cliff_drop_sec:
                return (
                    f"⚠️ ALERTE DÉGRADATION : Pilote {driver_number} - Chute de rythme prévue ! "
                    f"Perte estimée de {drop:.1f}s au prochain tour. Fin de vie des gommes probable."
                )

        return None

    def run_strategy_brief(
        self, 
        laps_data: List[Dict], 
        delta_df: pd.DataFrame, 
        predictor_model,
        target_driver: int, 
        rival_driver: int
    ) -> List[str]:
        """
        Génère un briefing stratégique complet (liste de messages).
        """
        alerts = []
        
        # 1. Analyse de l'undercut
        undercut_alert = self.analyze_undercut_opportunity(target_driver, rival_driver, delta_df)
        if undercut_alert:
            alerts.append(undercut_alert)
            
        # 2. Analyse de la dégradation
        cliff_alert = self.detect_tire_cliff(target_driver, predictor_model, laps_data)
        if cliff_alert:
            alerts.append(cliff_alert)
            
        return alerts

# Test de l'agent
if __name__ == "__main__":
    agent = StrategistAgent(pit_stop_loss_sec=24.0)
    print("Agent Stratège prêt. Les alertes ressembleront à :")
    print(agent.analyze_undercut_opportunity(
        driver_chasing=16, 
        driver_leading=1, 
        delta_df=pd.DataFrame({'cumulative_delta': [1.2]})
    ))