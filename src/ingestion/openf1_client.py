import requests
import json
from typing import Dict, List, Optional

BASE_URL = "https://api.openf1.org/v1"

class OpenF1Client:
    """Client pour interagir avec l'API OpenF1 (sessions, temps au tour, positions)."""

    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url

    def get_latest_session(self) -> Optional[Dict]:
        """Récupère la dernière session enregistrée ou en cours."""
        url = f"{self.base_url}/sessions?session_key=latest"
        response = requests.get(url)
        if response.status_code == 200 and response.json():
            return response.json()[0]
        return None

    def get_laps(self, session_key: int, driver_number: Optional[int] = None) -> List[Dict]:
        """Récupère les temps au tour pour une session donnée."""
        url = f"{self.base_url}/laps?session_key={session_key}"
        if driver_number:
            url += f"&driver_number={driver_number}"
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        return []

    def get_pit_stops(self, session_key: int) -> List[Dict]:
        """Récupère les arrêts aux stands de la session."""
        url = f"{self.base_url}/pit?session_key={session_key}"
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        return []

if __name__ == "__main__":
    client = OpenF1Client()
    session = client.get_latest_session()
    if session:
        print(f"Session trouvée : {session.get('meeting_name')} - {session.get('session_name')} ({session.get('year')})")
        session_key = session.get("session_key")
        laps = client.get_laps(session_key=session_key)
        print(f"Nombre de tours récupérés : {len(laps)}")
    else:
        print("Impossible de récupérer la dernière session.")