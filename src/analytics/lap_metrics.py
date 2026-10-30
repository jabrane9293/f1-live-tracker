import pandas as pd
from typing import List, Dict, Optional

# Dictionnaire de secours pour garantir que les noms/écuries s'affichent toujours
FALLBACK_DRIVERS = {
    # 1. McLaren Mastercard F1 Team
    1: {"full_name": "Lando NORRIS", "team_name": "McLaren", "team_colour": "FF8000"},
    4: {"full_name": "Lando NORRIS", "team_name": "McLaren", "team_colour": "FF8000"},
    81: {"full_name": "Oscar PIASTRI", "team_name": "McLaren", "team_colour": "FF8000"},

    # 2. Oracle Red Bull Racing
    3: {"full_name": "Max VERSTAPPEN", "team_name": "Red Bull Racing", "team_colour": "3671C6"},
    6: {"full_name": "Isack HADJAR", "team_name": "Red Bull Racing", "team_colour": "3671C6"},

    # 3. Scuderia Ferrari HP
    16: {"full_name": "Charles LECLERC", "team_name": "Ferrari", "team_colour": "E8002D"},
    44: {"full_name": "Lewis HAMILTON", "team_name": "Ferrari", "team_colour": "E8002D"},

    # 4. Mercedes-AMG Petronas F1 Team
    63: {"full_name": "George RUSSELL", "team_name": "Mercedes", "team_colour": "27F4D2"},
    12: {"full_name": "Kimi ANTONELLI", "team_name": "Mercedes", "team_colour": "27F4D2"},

    # 5. Visa Cash App Racing Bulls
    22: {"full_name": "Yuki TSUNODA", "team_name": "Racing Bulls", "team_colour": "6692FF"},
    30: {"full_name": "Liam LAWSON", "team_name": "Racing Bulls", "team_colour": "6692FF"},
    37: {"full_name": "Arvid LINDBLAD", "team_name": "Racing Bulls", "team_colour": "6692FF"},

    # 6. BWT Alpine F1 Team
    10: {"full_name": "Pierre GASLY", "team_name": "Alpine", "team_colour": "0093CC"},
    43: {"full_name": "Franco COLAPINTO", "team_name": "Alpine", "team_colour": "0093CC"},

    # 7. MoneyGram Haas F1 Team
    31: {"full_name": "Esteban OCON", "team_name": "Haas", "team_colour": "B6BABD"},
    87: {"full_name": "Oliver BEARMAN", "team_name": "Haas", "team_colour": "B6BABD"},

    # 8. Audi F1 Team
    27: {"full_name": "Nico HÜLKENBERG", "team_name": "Audi", "team_colour": "52E252"},
    5: {"full_name": "Gabriel BORTOLETO", "team_name": "Audi", "team_colour": "52E252"},

    # 9. Williams Racing
    23: {"full_name": "Alexander ALBON", "team_name": "Williams", "team_colour": "64C4FF"},
    55: {"full_name": "Carlos SAINZ", "team_name": "Williams", "team_colour": "64C4FF"},

    # 10. Aston Martin Cognizant F1 Team
    14: {"full_name": "Fernando ALONSO", "team_name": "Aston Martin", "team_colour": "229971"},
    18: {"full_name": "Lance STROLL", "team_name": "Aston Martin", "team_colour": "229971"},

    # 11. Cadillac Formula 1 Team
    77: {"full_name": "Valtteri BOTTAS", "team_name": "Cadillac", "team_colour": "FFD700"},
    11: {"full_name": "Sergio PEREZ", "team_name": "Cadillac", "team_colour": "FFD700"},

    # Réservistes & numéros historiques OpenF1 Replay
    38: {"full_name": "Oliver BEARMAN", "team_name": "Ferrari", "team_colour": "E8002D"},
    50: {"full_name": "Oliver BEARMAN", "team_name": "Haas", "team_colour": "B6BABD"},
    7: {"full_name": "Jack DOOHAN", "team_name": "Alpine", "team_colour": "0093CC"},
}

def format_lap_time(seconds: float) -> str:
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
            self.df['driver_number'] = pd.to_numeric(self.df['driver_number'], errors='coerce')
            cols = ['lap_duration', 'duration_sector_1', 'duration_sector_2', 'duration_sector_3']
            for c in cols:
                if c in self.df.columns:
                    self.df[c] = pd.to_numeric(self.df[c], errors='coerce')

    def get_driver_info(self, driver_number: int) -> Dict[str, str]:
        if not self.drivers_df.empty and 'driver_number' in self.drivers_df.columns:
            self.drivers_df['driver_number'] = pd.to_numeric(self.drivers_df['driver_number'], errors='coerce')
            match = self.drivers_df[self.drivers_df['driver_number'] == driver_number]
            if not match.empty:
                row = match.iloc[0]
                name = row.get('full_name') or row.get('broadcast_name') or str(driver_number)
                team = row.get('team_name') or "N/A"
                if name != str(driver_number) and team != "N/A":
                    return {"full_name": name, "team_name": team}
        return FALLBACK_DRIVERS.get(driver_number, {"full_name": f"Pilote #{driver_number}", "team_name": "Écurie N/A"})

    def get_leaderboard(self) -> pd.DataFrame:
        if self.df.empty or 'lap_duration' not in self.df.columns:
            return pd.DataFrame()

        valid_laps = self.df.copy()
        
        # On ne supprime QUE si le temps final au tour n'existe pas
        valid_laps = valid_laps.dropna(subset=['lap_duration'])
        
        if 'is_pit_out_lap' in valid_laps.columns:
            valid_laps = valid_laps[valid_laps['is_pit_out_lap'] != True]

        if valid_laps.empty:
            return pd.DataFrame()

        idx_bests = valid_laps.groupby('driver_number')['lap_duration'].idxmin()
        best_laps = valid_laps.loc[idx_bests].copy()

        names, teams = [], []
        for d_num in best_laps['driver_number']:
            info = self.get_driver_info(d_num)
            names.append(info["full_name"])
            teams.append(info["team_name"])

        best_laps['full_name'] = names
        best_laps['team_name'] = teams
        best_laps['Temps au tour'] = best_laps['lap_duration'].apply(format_lap_time)
        best_laps['Secteur 1'] = best_laps['duration_sector_1'].apply(format_lap_time)
        best_laps['Secteur 2'] = best_laps['duration_sector_2'].apply(format_lap_time)
        best_laps['Secteur 3'] = best_laps['duration_sector_3'].apply(format_lap_time)

        best_laps = best_laps.sort_values(by='lap_duration')
        best_laps['Position'] = range(1, len(best_laps) + 1)

        cols_display = ['Position', 'driver_number', 'full_name', 'team_name', 'Temps au tour', 'Secteur 1', 'Secteur 2', 'Secteur 3', 'lap_number']
        return best_laps[[c for c in cols_display if c in best_laps.columns]]

    def get_purple_sectors(self) -> Dict[str, Dict[str, str]]:
        """Retourne le temps violet ET le nom du pilote qui le détient."""
        purple = {}
        if self.df.empty:
            return purple
        for sector in ['duration_sector_1', 'duration_sector_2', 'duration_sector_3']:
            if sector in self.df.columns and not self.df[sector].dropna().empty:
                idx = self.df[sector].idxmin()
                best_row = self.df.loc[idx]
                d_num = best_row['driver_number']
                info = self.get_driver_info(d_num)
                
                purple[sector] = {
                    "time": format_lap_time(best_row[sector]),
                    "driver": info["full_name"]
                }
            else:
                purple[sector] = {"time": "-", "driver": "-"}
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
        
        comparison['time_A_str'] = comparison['lap_duration_A'].apply(format_lap_time)
        comparison['time_B_str'] = comparison['lap_duration_B'].apply(format_lap_time)
        comparison['delta_str'] = comparison['cumulative_delta'].apply(lambda x: f"{x:+.3f}s")
        
        return comparison.reset_index()