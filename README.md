# CloudBets 🏟️
**Análisis estadístico de apuestas deportivas**  
Proyecto — Computación en la Nube

---

## ¿Qué hace?

Muestra los partidos del día de las principales ligas del mundo y, cuando el usuario hace click en **ANALIZAR**, obtiene las estadísticas reales de los últimos 10 partidos de cada equipo (corners, goles, amarillas, offsides, tiros al arco, faltas) y genera **3 recomendaciones de apuesta**:

| Tipo | Mercado | Confianza esperada |
|------|---------|--------------------|
| 🟢 Segura | Corners Over/Under | ~75-92 % |
| 🟡 Intermedia | Goles / BTTS | ~55-72 % |
| 🔴 Casi imposible | Tarjetas amarillas | ~22-45 % |

---

## Estructura del proyecto

```
cloudbets/
├── main.py                        # App FastAPI + routers
├── config.py                      # Variables de entorno y constantes
├── requirements.txt
├── .env                           # Tu API key (no subir a git)
├── index.html                     # Frontend estático
└── app/
    ├── services/
    │   ├── football_api.py        # Comunicación con api-sports.io
    │   ├── data_analyzer.py       # Combina stats de ambos equipos
    │   └── prediction_service.py  # Genera las 3 apuestas
    └── api/
        ├── routes_matches.py      # GET /matches/today
        └── routes_analyze.py      # GET /analyze?fixture_id=<id>
```

---

## Instalación y uso

### 1. Clonar / descomprimir el proyecto

```bash
cd cloudbets
```

### 2. Crear el archivo `.env`

```
API_KEY=2ed485fa35d0cdeed1c6dc5068cde7be
BASE_URL=https://v3.football.api-sports.io
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Levantar el backend

```bash
uvicorn main:app --reload --port 8000
```

### 5. Abrir el frontend

Abrí `index.html` en el navegador (doble click o con Live Server en VS Code).  
El frontend se conecta automáticamente a `http://localhost:8000`.

---

## Endpoints de la API

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/` | Health check |
| GET | `/matches/today` | Partidos del día |
| GET | `/analyze?fixture_id=<id>` | Análisis completo de un partido |
| GET | `/analyze/demo` | Demo Boca vs River (sin consumir API) |

---

## API utilizada

**api-sports.io — API-Football** (plan gratuito: 100 llamadas/día)  
- Documentación: https://www.api-football.com/documentation-v3

### Ligas configuradas por defecto

| ID | Liga |
|----|------|
| 39 | Premier League |
| 140 | La Liga |
| 135 | Serie A |
| 78 | Bundesliga |
| 61 | Ligue 1 |
| 128 | Liga Profesional Argentina |
| 130 | Primera Nacional Argentina |

Se pueden agregar más en `config.py → IMPORTANT_LEAGUES`.

---

## Notas sobre el plan gratuito de api-sports.io

- **100 requests/día** en el plan free.
- Cada análisis de partido consume ~21 requests (1 fixture + 10×2 estadísticas).
- Usá el **endpoint `/analyze/demo`** para testear el frontend sin gastar cuota.

---

*Proyecto académico — no constituye asesoramiento financiero.*
