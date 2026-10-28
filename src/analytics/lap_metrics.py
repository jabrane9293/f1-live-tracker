import pandas as pd
from typing import List, Dict, Optional

def format_lap_time(seconds: float) -> str:
    """Convertit un temps en secondes vers le format officiel F1 (M:SS.mmm)."""
    if pd.isna(seconds) or seconds is None or seconds <= 0:
        return "-"
    minutes = int(seconds // 60)
    rem_seconds = seconds % 60
    if minutes > 0:
        return f"{minutes}:{rem_seconds:06.3f}"
    return f"{rem_seconds:.3f}"

class LapAnalyzer:
    def __init__(self, laps_data: List[Dict], drivers_data: Optional[List[Dict]] = None):
        self.df = pd.DataFrame(laps_data) if laps_data else pd.DataFrame()
        self.drivers_df = pd.DataFrame(drivers_data) if drivers_data else pd.DataFrame()

        if not self.df.empty:
            cols = ['lap_duration', 'duration_sector_1', 'duration_sector_2', 'duration_sector_3']
            for c in cols:
                if c in self.df.columns:
                    self.df[c] = pd.to_numeric(self.df[c], errors='coerce')

    def get_leaderboard(self) -> pd.DataFrame:
        """Leaderboard complet avec Nom, Écurie et temps au format M:SS.mmm."""
        if self.df.empty or 'lap_duration' not in self.df.columns:
            return pd.DataFrame()

        valid_laps = self.df.dropna(subset=['lap_duration'])
        if valid_laps.empty:
            return pd.DataFrame()

        idx_bests = valid_laps.groupby('driver_number')['lap_duration'].idxmin()
        best_laps = valid_laps.loc[idx_bests].copy()

        # Jointure avec les métadonnées pilotes
        if not self.drivers_df.empty and 'driver_number' in self.drivers_df.columns:
            # On supprime les doublons éventuels de drivers_df
            drivers_clean = self.drivers_df.drop_duplicates(subset=['driver_number'])
            best_laps = best_laps.merge(
                drivers_clean[['driver_number', 'full_name', 'team_name', 'team_colour']],
                on='driver_number',
                how='left'
            )
        else:
            best_laps['full_name'] = best_laps['driver_number'].astype(str)
            best_laps['team_name'] = "N/A"
            best_laps['team_colour'] = "FFFFFF"

        # Formatage des temps
        best_laps['Temps au tour'] = best_laps['lap_duration'].apply(format_lap_time)
        best_laps['Secteur 1'] = best_laps['duration_sector_1'].apply(format_lap_time)
        best_laps['Secteur 2'] = best_laps['duration_sector_2'].apply(format_lap_time)
        best_laps['Secteur 3'] = best_laps['duration_sector_3'].apply(format_lap_time)

        best_laps = best_laps.sort_values(by='lap_duration')
        best_laps['Position'] = range(1, len(best_laps) + 1)

        cols_display = ['Position', 'driver_number', 'full_name', 'team_name', 'Temps au tour', 'Secteur 1', 'Secteur 2', 'Secteur 3', 'lap_number']
        return best_laps[[c for c in cols_display if c in best_laps.columns]]

    def get_purple_sectors(self) -> Dict[str, str]:
        """Retourne les secteurs violets formates en M:SS.mmm."""
        purple = {}
        if self.df.empty:
            return purple
        for sector in ['duration_sector_1', 'duration_sector_2', 'duration_sector_3']:
            if sector in self.df.columns and not self.df[sector].dropna().empty:
                val = self.df[sector].min()
                purple[sector] = format_lap_time(val)
            else:
                purple[sector] = "-"
        return purple

    def calculate_driver_delta(self, driver_a: int, driver_b: int) -> pd.DataFrame:
        if self.df.empty or 'lap_duration' not in self.df.columns:
            return pd.DataFrame()

        df_a = self.df[self.df['driver_number'] == driver_a][['lap_number', 'lap_duration']].set_index('lap_number')
        df_b = self.df[self.df['driver_number'] == driver_b][['lap_number', 'lap_duration']].set_index('lap_number')
        
        comparison = df_a.join(df_b, lsuffix='_A', rsuffix='_B', how='inner')
        if comparison.empty:
            return pd.DataFrame()

        comparison['lap_delta'] = comparison['lap_duration_A'] - comparison['lap_duration_B']
        comparison['cumulative_delta'] = comparison['lap_delta'].cumsum()
        return comparison.reset_index()