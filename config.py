import os
from dotenv import load_dotenv

load_dotenv()

# ── API-Football ─────────────────────────────────────────────────────────────
# Clave de api-sports.io  (poner en .env como API_KEY=tu_clave)
API_KEY  = os.getenv("API_KEY", "2ed485fa35d0cdeed1c6dc5068cde7be")
BASE_URL = os.getenv("BASE_URL", "https://v3.football.api-sports.io")

# Ligas que mostramos en "Partidos de hoy"
# 39=Premier, 140=La Liga, 135=Serie A, 78=Bundesliga, 61=Ligue 1
# 128=Liga Profesional AR, 130=Primera Nacional AR
IMPORTANT_LEAGUES = {39, 140, 135, 78, 61, 128, 130, 2, 11, 13}

# Cantidad de partidos que se muestran en el mensaje de contexto al usuario
# (el análisis real usa los promedios de toda la temporada, no solo N partidos)
LAST_N_MATCHES = 10