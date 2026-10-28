import requests
import urllib3
from typing import Dict, List, Optional

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
BASE_URL = "https://api.openf1.org/v1"

class OpenF1Client:
    """Client OpenF1 optimisé pour les appels ciblés."""

    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url

    def _get(self, endpoint: str, params: Optional[Dict] = None) -> List[Dict]:
        try:
            url = f"{self.base_url}/{endpoint}"
            response = requests.get(url, params=params, verify=False, timeout=10)
            if response.status_code == 200 and response.json():
                return response.json()
        except Exception:
            pass
        return []

    def get_meetings(self, year: int = 2026) -> List[Dict]:
        return self._get("meetings", {"year": year})

    def get_sessions(self, meeting_key: int) -> List[Dict]:
        return self._get("sessions", {"meeting_key": meeting_key})

    def get_latest_session(self) -> Optional[Dict]:
        data = self._get("sessions", {"session_key": "latest"})
        return data[0] if data else None

    def get_drivers(self, session_key: int) -> List[Dict]:
        return self._get("drivers", {"session_key": session_key})

    def get_laps(self, session_key: int, driver_number: Optional[int] = None) -> List[Dict]:
        params = {"session_key": session_key}
        if driver_number:
            params["driver_number"] = driver_number
        return self._get("laps", params)

    def get_location(self, session_key: int, driver_number: Optional[int] = None) -> List[Dict]:
        """Récupère la télémétrie X, Y. Cibler un driver_number évite les timeouts API."""
        params = {"session_key": session_key}
        if driver_number:
            params["driver_number"] = driver_number
        return self._get("location", params)

    def get_weather(self, session_key: int) -> List[Dict]:
        return self._get("weather", {"session_key": session_key})

    def get_race_control(self, session_key: int) -> List[Dict]:
        return self._get("race_control", {"session_key": session_key})