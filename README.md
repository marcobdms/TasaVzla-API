# TasaVzla

> API FastAPI que expone la tasa oficial de cambio USD/VES y EUR/VES del Banco Central de Venezuela.

## Stack

- **FastAPI** + **uvicorn** (ASGI)
- **SQLAlchemy async** + **asyncpg** + **PostgreSQL**
- **httpx** + **BeautifulSoup4/lxml** para scraping
- **tenacity** para reintentos con backoff
- **APScheduler** para el job programado
- Deploy con **Coolify** / Docker

---

## Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/rate/usd` | Tasa USD/VES oficial BCV |
| GET | `/rate/eur` | Tasa EUR/VES oficial BCV |
| GET | `/health` | Liveness probe |
| GET | `/docs` | Swagger UI interactivo |

### Ejemplo de respuesta

```json
{
  "currency": "USD",
  "rate": 773.3125,
  "source": "bcv_direct",
  "rate_date": "2026-08-18",
  "fetched_at": "2026-08-18T19:02:14Z",
  "stale": false
}
```

**Valores de `source`:**
- `bcv_direct` — scrapeo exitoso desde bcv.org.ve
- `dolarapi_fallback` — BCV falló; dato obtenido de ve.dolarapi.com
- `cached_stale` — ambas fuentes fallaron; se devuelve el último valor guardado

---

## Cadena de Fallback

```
1. BCV directo (bcv.org.ve, div#dolar / div#euro, 3 reintentos + backoff)
        ↓ falla
2. dolarapi.com (ve.dolarapi.com/v1/dolares/oficial, /v1/euros)
        ↓ falla también
3. Último valor cacheado en DB con stale=true
```

---

## Scheduler

El job corre en horario laboral venezolano (VET = UTC−4), **días hábiles** (lun–vie):

| Hora VET | Hora UTC |
|----------|----------|
| 15:00 | 19:00 |
| 17:00 | 21:00 |
| 19:00 | 23:00 |

El BCV publica típicamente entre las 14h–16h VET; los tres runs cubren publicaciones tardías sin consultar cada minuto.

---

## Setup local

```bash
# 1. Clonar y entrar al directorio
git clone <repo> && cd TasaVzla

# 2. Levantar con Docker Compose
docker compose up --build

# 3. Probar
curl http://localhost:8000/rate/usd
curl http://localhost:8000/rate/eur
curl http://localhost:8000/health
```

Swagger UI disponible en `http://localhost:8000/docs`.

---

## Setup desarrollo sin Docker

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Editar .env con tu DATABASE_URL

uvicorn app.main:app --reload
```

---

## Deploy en Coolify

1. Conectar repositorio en Coolify → **Dockerfile** build
2. Agregar variable de entorno `DATABASE_URL` con la cadena de conexión a tu PostgreSQL (el que gestiona Coolify o externo)
3. Exponer puerto `8000`
4. Deploy → Coolify construye la imagen y levanta el contenedor

No se necesitan migraciones manuales: SQLAlchemy crea las tablas automáticamente en el primer arranque con `create_tables()`.

---

## Estructura del proyecto

```
TasaVzla/
├── app/
│   ├── __init__.py       # versión del paquete
│   ├── main.py           # FastAPI app, lifespan, rutas
│   ├── config.py         # settings (pydantic-settings)
│   ├── database.py       # engine async, sesión, create_tables
│   ├── models.py         # ORM model ExchangeRate
│   ├── schemas.py        # Pydantic response schemas
│   ├── crud.py           # upsert_rate, get_latest_rate
│   ├── scraper.py        # BCV scraper (httpx + BS4 + tenacity)
│   ├── fallback.py       # dolarapi.com fallback
│   ├── fetcher.py        # orquestador primary → fallback
│   └── scheduler.py      # APScheduler setup
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```
