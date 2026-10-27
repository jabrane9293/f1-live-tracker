import requests
import urllib3
from typing import Dict, List, Optional

# Désactiver les avertissements de sécurité pour ne pas polluer vos logs
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://api.openf1.org/v1"

class OpenF1Client:
    """Client pour interagir avec l'API OpenF1 en temps réel."""

    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url

    def get_latest_session(self) -> Optional[Dict]:
        """Récupère la dernière session enregistrée ou en cours."""
        url = f"{self.base_url}/sessions?session_key=latest"
        # Ajout de verify=False
        response = requests.get(url, verify=False)
        if response.status_code == 200 and response.json():
            return response.json()[0]
        return None

    def get_laps(self, session_key: int, driver_number: Optional[int] = None) -> List[Dict]:
        """Récupère les temps au tour et par secteur pour une session."""
        url = f"{self.base_url}/laps?session_key={session_key}"
        if driver_number:
            url += f"&driver_number={driver_number}"
        # Ajout de verify=False
        response = requests.get(url, verify=False)
        if response.status_code == 200:
            return response.json()
        return []

    def get_car_data(self, session_key: int, driver_number: int) -> List[Dict]:
        """Récupère la télémétrie en direct pour un pilote."""
        url = f"{self.base_url}/car_data?session_key={session_key}&driver_number={driver_number}"
        # Ajout de verify=False
        response = requests.get(url, verify=False)
        if response.status_code == 200:
            return response.json()
        return []