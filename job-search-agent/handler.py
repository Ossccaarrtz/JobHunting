try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from searcher import buscar_jobs
from storage import filtrar_nuevos, guardar_batch
from filter import filtrar_con_ia
from notifier import notificar


def lambda_handler(event, context):
    print("[handler] Iniciando búsqueda de jobs")

    # 1. Buscar jobs frescos en Jsearch
    jobs = buscar_jobs()
    if not jobs:
        print("[handler] Sin resultados de Jsearch")
        return {"procesados": 0, "notificados": 0}

    # 2. Filtrar duplicados contra DynamoDB
    jobs_nuevos = filtrar_nuevos(jobs)
    print(f"[handler] {len(jobs_nuevos)} jobs nuevos (no vistos antes)")

    if not jobs_nuevos:
        return {"procesados": 0, "notificados": 0}

    # 3. Filtrar por relevancia con Gemini
    jobs_relevantes = filtrar_con_ia(jobs_nuevos)

    # 4. Notificar por Telegram si hay matches
    if jobs_relevantes:
        notificar(jobs_relevantes)

    # 5. Guardar todos los jobs nuevos como vistos (relevantes o no)
    guardar_batch([job["id"] for job in jobs_nuevos])

    resultado = {"procesados": len(jobs_nuevos), "notificados": len(jobs_relevantes)}
    print(f"[handler] Finalizado: {resultado}")
    return resultado
