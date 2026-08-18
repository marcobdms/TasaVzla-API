# 🇻🇪 TasaVzla API

> API pública, rápida y confiable para consultar la **tasa oficial de cambio del Banco Central de Venezuela (BCV)** para **USD/VES** y **EUR/VES**.

Diseñada para desarrolladores y proyectos que necesitan integrar el tipo de cambio oficial venezolano sin sufrir por las caídas o la lentitud de la web del BCV.

---

## ⚡ ¿Por qué usar TasaVzla API?

- 🚀 **Respuesta ultrarrápida (sub-miliegundo):** Las tasas se sirven directamente desde caché en base de datos.
- 🛡️ **Alta disponibilidad:** Si el sitio web del BCV se cae o falla, la API sigue respondiendo con el último valor válido o activa fuentes de respaldo automáticas.
- 🔄 **Actualización automática:** Se sincroniza varias veces al día en días hábiles dentro del horario habitual de publicación del BCV (horario Venezuela).
- 🆓 **Fácil de consumir:** Respuestas JSON limpias, estandarizadas y sin necesidad de autenticación.

---

## 📡 Endpoints Disponibles

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `GET` | `/rate/usd` | Obtiene la tasa oficial actual de **Dólar (USD/VES)** |
| `GET` | `/rate/eur` | Obtiene la tasa oficial actual de **Euro (EUR/VES)** |
| `GET` | `/health` | Estado operativo de la API |
| `GET` | `/docs` | Documentación interactiva de Swagger UI |

---

## 📄 Estructura de Respuesta

### `GET /rate/usd`

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

### 📋 Detalle de los campos

| Campo | Tipo | Descripción |
| :--- | :--- | :--- |
| `currency` | `string` | Código de la moneda consultada (`USD` o `EUR`). |
| `rate` | `number` | Valor de la tasa de cambio en Bolívares (VES). |
| `source` | `string` | Origen del dato (`bcv_direct`, `dolarapi_fallback` o `cached_stale`). |
| `rate_date` | `string (YYYY-MM-DD)` | Fecha valor oficial reportada por el BCV. |
| `fetched_at` | `string (ISO 8601)` | Timestamp exacto en el que se sincronizó la tasa. |
| `stale` | `boolean` | `true` solo en caso extremo de que fallen todas las fuentes y se devuelva un valor anterior. |

---

## 💻 Ejemplos de Integración

### JavaScript / TypeScript (Fetch)
```javascript
// Obtener tasa USD
async function getTasaDolar() {
  try {
    const res = await fetch("https://<TU-DOMINIO>/rate/usd");
    const data = await res.json();
    console.log(`Tasa USD: ${data.rate} VES (Fecha: ${data.rate_date})`);
    return data.rate;
  } catch (error) {
    console.error("Error al obtener la tasa:", error);
  }
}
```

### Python (httpx / requests)
```python
import httpx

response = httpx.get("https://<TU-DOMINIO>/rate/usd")
data = response.json()

print(f"1 USD = {data['rate']} VES (Fuente: {data['source']})")
```

### cURL
```bash
curl -X GET "https://<TU-DOMINIO>/rate/usd" -H "Accept: application/json"
```

---

## 🕒 Horario de Actualización

La API corre tareas automáticas de sincronización en días hábiles (lunes a viernes) en los horarios clave de publicación del BCV:

- **15:00 VET** (Hora de Venezuela)
- **17:00 VET**
- **19:00 VET**

---

## 🛠️ Documentación Interactiva

Puedes probar todos los endpoints y ver los esquemas en tiempo real directamente desde tu navegador en:

👉 `https://<TU-DOMINIO>/docs`
