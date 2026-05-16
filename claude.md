# Job Search Agent — Contexto del Proyecto

## Propósito

Agente automatizado personal que busca internships/jobs de software engineering que matcheen el perfil del usuario, filtra con IA los más relevantes, y notifica por Telegram solo los nuevos. Corre sin intervención humana.

## Arquitectura

```
EventBridge (cada 6hrs)
  → Lambda (Python)
    → Jsearch API        — buscar jobs frescos
    → Gemini API         — filtrar relevancia con IA
    → DynamoDB           — evitar notificar duplicados
    → Telegram Bot API   — notificar solo jobs nuevos
```

## Stack

| Componente | Servicio | Tier |
|---|---|---|
| Scheduler | AWS EventBridge | Free |
| Runtime | AWS Lambda (Python 3.12) | Free (1M invocaciones/mes) |
| Búsqueda de jobs | Jsearch API (RapidAPI) | Free (200 req/mes) |
| Filtrado IA | Google Gemini API | Free |
| Persistencia | AWS DynamoDB | Free (25GB) |
| Notificaciones | Telegram Bot API | Gratis siempre |

**Costo estimado total: $0/mes**

## Estructura de archivos

```
job-search-agent/
├── CLAUDE.md               # este archivo
├── handler.py              # entry point del Lambda
├── searcher.py             # integración Jsearch API
├── filter.py               # filtrado con Gemini
├── storage.py              # operaciones DynamoDB
├── notifier.py             # integración Telegram
├── profile.json            # perfil del usuario (fuente de verdad)
└── requirements.txt
```

## Perfil del usuario (profile.json)

El perfil es la fuente de verdad para el filtrado. Refleja el CV real del usuario.

```json
{
  "nombre": "Oscar Castillo",
  "rol_buscado": "Software Engineer Intern",
  "skills": ["Python", "FastAPI", "Flask", "React", "AWS", "PostgreSQL", "SQLAlchemy", "Docker"],
  "ciudadania": "USA/Mexico",
  "no_requiere_visa_sponsorship": true,
  "disponibilidad": "Verano 2026",
  "hackathons": ["NASA Space Apps 1st Place", "Daimler Hackathon 1st Place"],
  "idiomas": ["Español", "Inglés"],
  "preferencias": {
    "ubicacion": ["Remote", "USA"],
    "tipo": ["Internship", "New Grad"],
    "empresas_target": ["Stripe", "Cloudflare", "startups YC"],
    "evitar": ["requiere_sponsorship", "sin_remote"]
  }
}
```

## Módulos

### handler.py — Entry point

Orquesta el flujo completo. Es lo único que Lambda ejecuta.

```python
def lambda_handler(event, context):
    jobs = buscar_jobs()
    jobs_nuevos = filtrar_duplicados(jobs)
    jobs_relevantes = filtrar_con_ia(jobs_nuevos)
    if jobs_relevantes:
        notificar(jobs_relevantes)
    guardar_vistos(jobs_nuevos)
    return {"procesados": len(jobs_nuevos), "notificados": len(jobs_relevantes)}
```

### searcher.py — Jsearch API

- Queries: `"software engineer intern remote USA"`, `"backend engineer intern"`
- Paginar solo si free tier lo permite (máx 200 req/mes → ~1-2 páginas por corrida)
- Retornar lista de dicts con: `id, titulo, empresa, ubicacion, url, descripcion, fecha_publicacion`

### filter.py — Gemini API

- Cargar `profile.json` una sola vez al inicio del módulo
- Prompt conciso — Gemini cobra por tokens
- Respuesta esperada: `{"match": true/false, "razon": "string corta"}`
- Procesar jobs en batch si es posible para reducir llamadas a la API

```python
PROMPT_TEMPLATE = """
Perfil: {perfil}
Job: {titulo} en {empresa} — {descripcion_corta}

¿Es relevante para este perfil? Responde SOLO JSON: {{"match": true/false, "razon": "max 20 palabras"}}
"""
```

### storage.py — DynamoDB

Tabla: `job-search-seen`
- Partition key: `job_id` (string)
- TTL: 30 días (para no acumular registros viejos infinitamente)
- Operaciones: `existe(job_id)` y `guardar(job_id)`

> Activar TTL en DynamoDB para evitar que la tabla crezca indefinidamente.

### notifier.py — Telegram

- Usar `sendMessage` con `parse_mode=Markdown`
- Agrupar jobs en un solo mensaje si son varios (evitar spam)
- Si son más de 5 jobs, mandar resumen en vez de lista completa

```
🔔 *3 nuevos jobs encontrados*

1. *Backend Intern* — Stripe (Remote)
   Match: Usa FastAPI y Python ✅
   🔗 [Aplicar](url)

2. *SWE Intern* — Cloudflare (Remote)
   ...
```

## Buenas prácticas AWS

### Lambda
- **Timeout**: 60 segundos máximo (el flujo completo no debería tardar más de 30s)
- **Memory**: 256MB es suficiente, no subir sin medir primero
- **Variables de entorno**: todas las API keys van aquí, nunca hardcodeadas
- **Dependencias**: usar Lambda Layers para las dependencias Python y reducir el cold start

### EventBridge
- Schedule: `rate(6 hours)` — 4 veces al día, 120 invocaciones/mes
- Nunca usar `rate(1 minute)` ni similares por error — revisar siempre antes de deployar

### DynamoDB
- **On-demand billing** (pay-per-request), no provisioned — con 4 lecturas/escrituras al día el costo es $0
- **TTL habilitado** en el atributo `expires_at` para auto-limpiar registros viejos
- No usar Scan, siempre GetItem con el job_id exacto

### Secrets
- API keys en **AWS Systems Manager Parameter Store** (gratis) o variables de entorno del Lambda
- Nunca en el código ni en el repo

## Variables de entorno requeridas

```
JSEARCH_API_KEY=...
GEMINI_API_KEY=...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
DYNAMODB_TABLE=job-search-seen
AWS_REGION=us-east-1
```

## Decisiones de diseño

- **Gemini sobre Ollama**: el Lambda no puede correr modelos locales. Gemini free tier es suficiente para filtrar ~20 jobs por corrida.
- **Jsearch sobre scraping**: LinkedIn bloquea IPs de AWS. Jsearch agrega múltiples fuentes sin riesgo de ban.
- **DynamoDB sobre SQLite**: Lambda es stateless, no hay filesystem persistente entre invocaciones.
- **Telegram sobre WhatsApp**: API gratuita, sin aprobaciones, sin costo por mensaje.
- **JSON sobre PDF para el perfil**: el LLM no necesita formato visual, solo información estructurada.

## Flujo de desarrollo local

```bash
# Instalar dependencias
pip install -r requirements.txt

# Correr localmente simulando el evento de EventBridge
python -c "from handler import lambda_handler; lambda_handler({}, {})"

# Deploy
zip -r function.zip . && aws lambda update-function-code \
  --function-name job-search-agent \
  --zip-file fileb://function.zip
```

## Siguientes mejoras (backlog)

- [ ] Filtrar por fecha de publicación (solo jobs de últimas 24hrs)
- [ ] RSS feeds de empresas target específicas (Greenhouse/Lever) para más velocidad
- [ ] Score de relevancia 1-10 en vez de solo match/no match
- [ ] Comando `/buscar` en Telegram para trigger manual