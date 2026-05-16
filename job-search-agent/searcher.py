import os
import requests

JSEARCH_URL = "https://jsearch.p.rapidapi.com/search"
HEADERS = {
    "X-RapidAPI-Key": os.environ["JSEARCH_API_KEY"],
    "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
}

# Queries optimizadas para el perfil — 2 queries x 1 página = 2 req por corrida
QUERIES = [
    "software engineer intern remote USA",
    "backend engineer intern remote",
]


def _buscar_query(query: str, pagina: int = 1) -> list[dict]:
    """Ejecuta una query en Jsearch y retorna lista de jobs normalizados."""
    params = {
        "query": query,
        "page": str(pagina),
        "num_pages": "1",
        "date_posted": "today",
    }
    try:
        response = requests.get(JSEARCH_URL, headers=HEADERS, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        print(f"[searcher] Error en query '{query}': {e}")
        return []

    jobs = []
    for item in data.get("data", []):
        jobs.append({
            "id": item.get("job_id", ""),
            "titulo": item.get("job_title", ""),
            "empresa": item.get("employer_name", ""),
            "ubicacion": _extraer_ubicacion(item),
            "url": item.get("job_apply_link") or item.get("job_google_link", ""),
            "descripcion": (item.get("job_description") or "")[:1500],
            "fecha_publicacion": item.get("job_posted_at_datetime_utc", ""),
            "es_remoto": item.get("job_is_remote", False),
        })
    return jobs


def _extraer_ubicacion(item: dict) -> str:
    ciudad = item.get("job_city") or ""
    estado = item.get("job_state") or ""
    pais = item.get("job_country") or ""
    if item.get("job_is_remote"):
        return "Remote"
    partes = [p for p in [ciudad, estado, pais] if p]
    return ", ".join(partes) if partes else "N/A"


def buscar_jobs() -> list[dict]:
    """
    Ejecuta todas las queries y retorna jobs únicos por job_id.
    Máx 2 requests por corrida para respetar el free tier de 200 req/mes.
    """
    todos = []
    vistos = set()

    for query in QUERIES:
        jobs = _buscar_query(query)
        for job in jobs:
            if job["id"] and job["id"] not in vistos:
                vistos.add(job["id"])
                todos.append(job)

    print(f"[searcher] {len(todos)} jobs únicos encontrados")
    return todos
