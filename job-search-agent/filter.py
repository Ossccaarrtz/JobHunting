import os
import json
import re
import groq

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
        _client = groq.Groq(api_key=os.environ["GROQ_API_KEY"])
    return _client


def _evaluar_job(job: dict) -> tuple[bool, dict | None]:
    """
    Evalúa un job con Groq (llama-3.1-8b-instant).
    Retorna (evaluado, job_o_none):
      - (True, job)  → Groq respondió y hace match
      - (True, None) → Groq respondió pero no hace match
      - (False, None)→ Error de API, no se evaluó
    """
    prompt = PROMPT_TEMPLATE.format(
        perfil=json.dumps(_PERFIL_RESUMIDO, ensure_ascii=False),
        titulo=job["titulo"],
        empresa=job["empresa"],
        ubicacion=job["ubicacion"],
        descripcion=job["descripcion"][:800],
    )
    try:
        response = _get_client().chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100,
        )
        texto = response.choices[0].message.content.strip()
        texto = re.sub(r"^```(?:json)?\s*", "", texto)
        texto = re.sub(r"\s*```$", "", texto)
        resultado = json.loads(texto)
        if resultado.get("match"):
            job["razon_match"] = resultado.get("razon", "")
            return True, job
        return True, None
    except Exception as e:
        print(f"[filter] Error evaluando '{job['titulo']}' en {job['empresa']}: {e}")
        return False, None


def filtrar_con_ia(jobs: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Filtra la lista de jobs con Groq.
    Retorna (relevantes, evaluados_exitosamente).
    Solo los evaluados exitosamente deben marcarse como vistos en DynamoDB.
    Los que tuvieron error de API se omiten para que se reintenten en la próxima corrida.
    """
    if not jobs:
        return [], []

    relevantes = []
    evaluados = []
    for job in jobs:
        ok, resultado = _evaluar_job(job)
        if ok:
            evaluados.append(job)
            if resultado is not None:
                relevantes.append(resultado)

    errores = len(jobs) - len(evaluados)
    print(f"[filter] {len(relevantes)}/{len(evaluados)} jobs pasaron el filtro de IA"
          + (f" ({errores} errores de API, se reintentarán)" if errores else ""))
    return relevantes, evaluados
