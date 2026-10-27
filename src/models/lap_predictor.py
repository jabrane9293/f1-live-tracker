import pandas as pd
import numpy as np
import logging
from sklearn.ensemble import RandomForestRegressor
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class LapPredictor:
    """
    Modèle de prédiction des temps au tour en temps réel.
    S'entraîne à la volée sur les données de la course en cours.
    """

    def __init__(self):
        # Un modèle léger, rapide à ré-entraîner à chaque nouveau tour
        self.model = RandomForestRegressor(n_estimators=50, max_depth=5, random_state=42)
        self.is_trained = False
        self.feature_cols = ['lap_number', 'last_lap_time', 'rolling_avg_3']

    def _prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Génère les features nécessaires à la prédiction.
        """
        # On s'assure que les données sont triées par pilote et par tour
        df = df.sort_values(by=['driver_number', 'lap_number']).copy()
        
        # Feature 1 : Le temps du tour précédent (inertie / rythme actuel)
        df['last_lap_time'] = df.groupby('driver_number')['lap_duration'].shift(1)
        
        # Feature 2 : Moyenne glissante des 3 derniers tours (lisse les erreurs de pilotage/trafic)
        df['rolling_avg_3'] = df.groupby('driver_number')['last_lap_time'].transform(
            lambda x: x.rolling(window=3, min_periods=1).mean()
        )
        
        # On supprime les lignes avec des NaN (généralement le premier tour)
        return df.dropna(subset=['lap_duration', 'last_lap_time'])

    def train(self, laps_data: List[Dict]):
        """
        Entraîne (ou ré-entraîne) le modèle sur l'historique disponible de la course.
        """
        if not laps_data:
            logger.warning("Pas de données pour l'entraînement.")
            return

        df_raw = pd.DataFrame(laps_data)
        if 'lap_duration' not in df_raw.columns:
            return

        df_features = self._prepare_features(df_raw)
        
        if len(df_features) < 10:
            logger.debug("Pas assez de données pour entraîner le modèle (<10 samples).")
            return

        X = df_features[self.feature_cols]
        y = df_features['lap_duration']

        self.model.fit(X, y)
        self.is_trained = True
        logger.info(f"Modèle ré-entraîné sur {len(X)} échantillons.")

    def predict_next_lap(self, laps_data: List[Dict], driver_number: int) -> Optional[float]:
        """
        Prédit le chrono du prochain tour pour un pilote spécifique.
        """
        if not self.is_trained or not laps_data:
            return None

        df_raw = pd.DataFrame(laps_data)
        driver_df = df_raw[df_raw['driver_number'] == driver_number]
        
        if driver_df.empty:
            return None

        # Préparation du vecteur pour le tour N+1
        driver_df = driver_df.sort_values(by='lap_number')
        last_lap_num = driver_df['lap_number'].iloc[-1]
        
        # On crée une ligne fictive représentant le prochain tour pour générer ses features
        future_lap = pd.DataFrame({
            'driver_number': [driver_number],
            'lap_number': [last_lap_num + 1],
            'lap_duration': [np.nan]
        })
        
        extended_df = pd.concat([driver_df, future_lap], ignore_index=True)
        extended_features = self._prepare_features(extended_df)
        
        # Le dernier élément correspond à notre tour à prédire
        next_lap_features = extended_features[self.feature_cols].iloc[[-1]]
        
        prediction = self.model.predict(next_lap_features)[0]
        return round(prediction, 3)

# Test rapide du module
if __name__ == "__main__":
    # Simulation de données factices pour tester la mécanique
    mock_data = [
        {"driver_number": 1, "lap_number": 1, "lap_duration": 92.5},
        {"driver_number": 1, "lap_number": 2, "lap_duration": 90.1},
        {"driver_number": 1, "lap_number": 3, "lap_duration": 89.8},
        {"driver_number": 1, "lap_number": 4, "lap_duration": 89.9},
        {"driver_number": 1, "lap_number": 5, "lap_duration": 90.3}, # Début de dégradation
    ]
    
    predictor = LapPredictor()
    predictor.train(mock_data)
    
    pred = predictor.predict_next_lap(mock_data, 1)
    print(f"Prédiction pour le tour 6 : {pred} secondes")