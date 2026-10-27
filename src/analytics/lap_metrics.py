import pandas as pd
from typing import List, Dict, Optional

class LapAnalyzer:
    """
    Moteur de calcul analytique pour les temps au tour.
    Utilise Pandas pour vectoriser les calculs (deltas, meilleurs secteurs) 
    à partir des données brutes en cache.
    """

    def __init__(self, laps_data: List[Dict]):
        # Création du DataFrame et nettoyage basique
        if laps_data:
            self.df = pd.DataFrame(laps_data)
            # Sécurisation des types numériques (OpenF1 peut parfois renvoyer du None ou des strings)
            numeric_cols = ['lap_duration', 'duration_sector_1', 'duration_sector_2', 'duration_sector_3']
            for col in numeric_cols:
                if col in self.df.columns:
                    self.df[col] = pd.to_numeric(self.df[col], errors='coerce')
        else:
            self.df = pd.DataFrame()

    def get_best_laps(self) -> pd.DataFrame:
        """Retourne le meilleur temps absolu pour chaque pilote."""
        if self.df.empty or 'lap_duration' not in self.df.columns:
            return pd.DataFrame()
        
        # Filtre les tours valides (non nuls)
        valid_laps = self.df.dropna(subset=['lap_duration'])
        if valid_laps.empty:
            return pd.DataFrame()
            
        # Trouve l'index du tour le plus rapide pour chaque pilote
        idx_bests = valid_laps.groupby('driver_number')['lap_duration'].idxmin()
        best_laps = valid_laps.loc[idx_bests]
        
        # Tri du plus rapide au plus lent (leaderboard)
        return best_laps[['driver_number', 'lap_duration', 'lap_number']].sort_values(by='lap_duration')

    def get_purple_sectors(self) -> Dict[str, float]:
        """Retourne les meilleurs temps absolus pour chaque secteur (S1, S2, S3)."""
        if self.df.empty:
            return {}
        
        purple_sectors = {}
        for sector in ['duration_sector_1', 'duration_sector_2', 'duration_sector_3']:
            if sector in self.df.columns:
                purple_sectors[sector] = self.df[sector].min()
        return purple_sectors

    def calculate_driver_delta(self, driver_a: int, driver_b: int) -> pd.DataFrame:
        """
        Calcule l'écart de temps (delta) tour par tour entre deux pilotes.
        Idéal pour tracer un graphique de rattrapage en temps réel sur l'UI.
        """
        if self.df.empty or 'lap_duration' not in self.df.columns:
            return pd.DataFrame()

        # Isoler les dataframes des deux pilotes
        df_a = self.df[self.df['driver_number'] == driver_a][['lap_number', 'lap_duration']].set_index('lap_number')
        df_b = self.df[self.df['driver_number'] == driver_b][['lap_number', 'lap_duration']].set_index('lap_number')
        
        # Jointure inner sur le numéro de tour (on ne compare que les tours complétés par les deux)
        comparison = df_a.join(df_b, lsuffix='_A', rsuffix='_B', how='inner')
        
        if comparison.empty:
            return pd.DataFrame()

        # Delta ponctuel par tour (négatif = A est plus rapide que B sur ce tour)
        comparison['lap_delta'] = comparison['lap_duration_A'] - comparison['lap_duration_B']
        
        # Delta cumulé (évolution de l'écart global au fil du relais)
        comparison['cumulative_delta'] = comparison['lap_delta'].cumsum()
        
        return comparison.reset_index()