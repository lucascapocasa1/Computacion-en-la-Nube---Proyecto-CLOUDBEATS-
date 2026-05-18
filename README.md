# CloudBets 🏟️

**Análisis estadístico de apuestas deportivas con Value Betting**  
Proyecto para la materia _Computación en la Nube_ · Universidad

---

## ¿Qué hace?

CloudBets obtiene los partidos del día de las principales ligas del mundo, analiza las estadísticas históricas de ambos equipos y calcula qué apuestas tienen **valor esperado (EV) positivo** comparando probabilidades propias contra las cuotas reales de Bet365.

### Funcionalidades principales

| Feature                | Descripción                                                               |
| ---------------------- | ------------------------------------------------------------------------- |
| 📅 Partidos del día    | Muestra los partidos pendientes y en vivo de hoy (hora ART)               |
| 📊 Estadísticas        | Promedios de temporada: corners, goles, tarjetas, tiros, faltas, offsides |
| 💰 Value Betting       | EV real con cuotas de Bet365 cuando están disponibles                     |
| 👥 Alineaciones        | Once titular en campo visual (~1h antes del partido)                      |
| ⚡ Eventos             | Línea de tiempo de goles, tarjetas y sustituciones                        |
| 📡 Stats en vivo       | Posesión, tiros, corners actualizados cada 60s en partidos en curso       |
| 🏆 Tabla de posiciones | Consulta la tabla de cualquier liga sin salir de la app                   |
| 🕐 Historial           | Últimos 10 análisis guardados en localStorage                             |
| 📄 Exportar PDF        | Resumen del análisis para imprimir o compartir                            |

---

## Requisitos

- Python 3.11+
- API key de [api-football.com](https://www.api-football.com/) (plan gratuito: 100 req/día)

---

## Instalación

```bash
# 1. Clonar el repositorio
git clone https://github.com/tu-usuario/cloudbets.git
cd cloudbets

# 2. Crear entorno virtual (recomendado)
python -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar variables de entorno
cp .env.example .env
# Editar .env y poner tu API key
```

### Archivo `.env`

```env
API_KEY=tu_api_key_de_api_football
BASE_URL=https://v3.football.api-sports.io
```

---

## Uso

```bash
uvicorn main:app --reload --port 8000
```

Luego abrir `index.html` en el navegador (doble click o con Live Server en VS Code).

> El frontend se conecta a `http://localhost:8000`. No requiere servidor web propio.

---

## Estructura del proyecto

```
cloudbets/
├── main.py                          # App FastAPI
├── config.py                        # Variables de entorno y constantes
├── requirements.txt
├── .env                             # API key (NO subir a git)
├── .gitignore
├── index.html                       # Frontend
├── styles.css                       # Estilos
├── script.js                        # Lógica del frontend
└── app/
    ├── api/
    │   ├── routes_matches.py        # GET /matches/today
    │   └── routes_analyze.py        # GET /analyze y derivados
    └── services/
        ├── football_api.py          # Comunicación con api-football
        ├── data_analyzer.py         # Combina stats de ambos equipos
        └── prediction_service.py    # Motor de value betting
```

---

## Endpoints de la API

| Método | Endpoint                              | Descripción                                            |
| ------ | ------------------------------------- | ------------------------------------------------------ |
| GET    | `/`                                   | Health check                                           |
| GET    | `/matches/today`                      | Partidos del día (solo pendientes y en vivo, hora ART) |
| GET    | `/analyze?fixture_id=<id>`            | Stats de temporada + recomendaciones EV                |
| GET    | `/analyze/lineups?fixture_id=<id>`    | Alineaciones del partido                               |
| GET    | `/analyze/events?fixture_id=<id>`     | Eventos: goles, tarjetas, sustituciones                |
| GET    | `/analyze/live-stats?fixture_id=<id>` | Stats en tiempo real                                   |
| GET    | `/analyze/standings?league_id=<id>`   | Tabla de posiciones                                    |

---

## Ligas soportadas

| ID  | Liga                       |
| --- | -------------------------- |
| 39  | Premier League             |
| 140 | La Liga                    |
| 135 | Serie A                    |
| 78  | Bundesliga                 |
| 61  | Ligue 1                    |
| 2   | Champions League           |
| 11  | Copa Libertadores          |
| 13  | Copa Sudamericana          |
| 128 | Liga Profesional Argentina |
| 130 | Primera Nacional Argentina |

Para agregar más ligas, editar `IMPORTANT_LEAGUES` en `config.py`.

---

## Motor de Value Betting

### Con cuotas reales (Bet365)

```
EV = probabilidad_propia × cuota_bet365 - 1
EV > 0  →  apuesta con valor a largo plazo
EV < 0  →  la casa tiene ventaja
```

### Sin cuotas reales

Se muestra la **probabilidad estimada** y la **cuota justa** (`1 / prob`).  
El EV aparece como `N/D` — nunca se fabrica un número falso.

### Modelos estadísticos

- **Poisson** para eventos de conteo: corners, goles, offsides
- **Normal** para eventos con alta varianza: tarjetas, faltas, tiros

### Factor local/visitante

Las stats del equipo local se extraen de sus partidos **de local**,  
y las del visitante de sus partidos **de visita**.

---

## Limitaciones del plan gratuito de api-football

- **100 requests/día** — cada análisis consume ~13 llamadas
- **Estadísticas históricas hasta temporada 2024** — fallback automático si la temporada actual no tiene datos
- **Cuotas de Bet365** disponibles con 1–3 días de anticipación para ligas principales

---

## Tecnologías

**Backend:** Python 3.11 · FastAPI · uvicorn · requests  
**Frontend:** HTML5 · CSS3 · JavaScript (vanilla, sin frameworks)  
**Datos:** [api-football.com v3](https://www.api-football.com/documentation-v3)

---

## Archivo `.gitignore` recomendado

```
.env
__pycache__/
*.pyc
venv/
.venv/
```

---

> ⚠️ **Aviso legal:** CloudBets es un proyecto académico. Las recomendaciones son estimaciones estadísticas y no garantizan ganancias. Apostá con responsabilidad.
