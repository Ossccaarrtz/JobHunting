import os
import json
import re
from google import genai
from google.genai import types

# Cargar perfil una sola vez al inicio del módulo
_PROFILE_PATH = os.path.join(os.path.dirname(__file__), "profile.json")
with open(_PROFILE_PATH, "r", encoding="utf-8") as f:
    _PERFIL = json.load(f)

_PERFIL_RESUMIDO = {
    "rol_buscado": _PERFIL["rol_buscado"]["titulos"],
    "skills": _PERFIL["skills"],
    "ciudadania": _PERFIL["personal"]["ciudadania"],
    "requiere_visa_sponsorship": _PERFIL["personal"]["requiere_visa_sponsorship"],
    "ubicacion_preferida": _PERFIL["rol_buscado"]["ubicacion_preferida"],
    "criterios": _PERFIL["criterios_match_ia"],
}

PROMPT_TEMPLATE = """\
Perfil del candidato:
{perfil}

Job a evaluar:
Título: {titulo}
Empresa: {empresa}
Ubicación: {ubicacion}
Descripción: {descripcion}

¿Es este job relevante para el candidato? Considera los must_have y dealbreakers.
Responde SOLO con JSON válido, sin markdown: {{"match": true/false, "razon": "max 20 palabras"}}"""


_client = None


def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    return _client


def _evaluar_job(job: dict) -> dict | None:
    """Evalúa un job con Gemini. Retorna el job con campo 'razon' si hace match, None si no."""
    prompt = PROMPT_TEMPLATE.format(
        perfil=json.dumps(_PERFIL_RESUMIDO, ensure_ascii=False),
        titulo=job["titulo"],
        empresa=job["empresa"],
        ubicacion=job["ubicacion"],
        descripcion=job["descripcion"][:800],
    )
    try:
        response = _get_client().models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt,
        )
        texto = response.text.strip()
        # Limpiar posible markdown que Gemini agregue
        texto = re.sub(r"^```(?:json)?\s*", "", texto)
        texto = re.sub(r"\s*```$", "", texto)
        resultado = json.loads(texto)
        if resultado.get("match"):
            job["razon_match"] = resultado.get("razon", "")
            return job
        return None
    except Exception as e:
        print(f"[filter] Error evaluando '{job['titulo']}' en {job['empresa']}: {e}")
        return None


def filtrar_con_ia(jobs: list[dict]) -> list[dict]:
    """
    Filtra la lista de jobs con Gemini.
    Retorna solo los jobs relevantes con campo 'razon_match' agregado.
    """
    if not jobs:
        return []

    relevantes = []
    for job in jobs:
        resultado = _evaluar_job(job)
        if resultado:
            relevantes.append(resultado)

    print(f"[filter] {len(relevantes)}/{len(jobs)} jobs pasaron el filtro de IA")
    return relevantes
