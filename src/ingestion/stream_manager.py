import asyncio
import logging
from typing import Dict, List, Optional
from src.ingestion.openf1_client import OpenF1Client

# Configuration basique du logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class StreamManager:
    """
    Gère le flux de données en temps réel en effectuant un polling asynchrone 
    sur le client OpenF1 et en maintenant un cache en mémoire pour l'application.
    """

    def __init__(self, poll_interval: int = 5):
        self.client = OpenF1Client()
        self.poll_interval = poll_interval
        
        # État en mémoire (Cache)
        self.current_session: Optional[Dict] = None
        self.laps_cache: List[Dict] = []
        self.car_data_cache: Dict[int, List[Dict]] = {} # Clé: driver_number
        
        # Contrôle de la boucle asynchrone
        self._is_running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        """Démarre la boucle de polling en arrière-plan."""
        if self._is_running:
            return
        
        logger.info("Initialisation du StreamManager...")
        # Récupération de la session active avant de lancer la boucle
        self.current_session = await asyncio.to_thread(self.client.get_latest_session)
        
        if not self.current_session:
            logger.warning("Aucune session active trouvée. Le polling tournera à vide. ")
        else:
            logger.info(f"Session accrochée : {self.current_session.get('session_name')}")

        self._is_running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info(f"Boucle de polling démarrée (Intervalle: {self.poll_interval}s).")

    async def stop(self):
        """Arrête proprement la boucle de polling."""
        self._is_running = False
        if self._task:
            self._task.cancel()
            logger.info("Boucle de polling arrêtée.")

    async def _poll_loop(self):
        """Boucle principale de récupération des données."""
        while self._is_running:
            try:
                if self.current_session:
                    session_key = self.current_session.get("session_key")
                    
                    # Offload la requête HTTP bloquante dans un thread séparé
                    new_laps = await asyncio.to_thread(self.client.get_laps, session_key)
                    
                    if new_laps:
                        # Dans une version optimisée, on filtrerait uniquement les nouveaux tours
                        self.laps_cache = new_laps 
                        logger.debug(f"Mise à jour : {len(self.laps_cache)} tours en cache.")
            
            except Exception as e:
                logger.error(f"Erreur lors du polling OpenF1 : {e}")
            
            # Attente avant la prochaine requête
            await asyncio.sleep(self.poll_interval)

    def get_latest_laps(self) -> List[Dict]:
        """Retourne les temps au tour actuellement en cache."""
        return self.laps_cache

    def get_session_info(self) -> Optional[Dict]:
        """Retourne les métadonnées de la session en cours."""
        return self.current_session


# Test rapide du module si exécuté directement
if __name__ == "__main__":
    async def test_run():
        manager = StreamManager(poll_interval=2)
        await manager.start()
        await asyncio.sleep(5)  # Laisse tourner 5 secondes
        laps = manager.get_latest_laps()
        print(f"Test terminé. Nombre de tours en cache : {len(laps)}")
        await manager.stop()

    asyncio.run(test_run())