try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from searcher import buscar_jobs
from storage import filtrar_nuevos, guardar_batch, heartbeat_enviado_hoy, guardar_heartbeat
from filter import filtrar_con_ia
from notifier import notificar, notificar_sin_matches, notificar_heartbeat


def lambda_handler(event, context):
    print("[handler] Iniciando búsqueda de jobs")

    jobs_encontrados = 0
    jobs_nuevos_count = 0
    jobs_evaluados_count = 0
    jobs_notificados_count = 0

    # 1. Buscar jobs frescos en Jsearch
    jobs = buscar_jobs()
    jobs_encontrados = len(jobs)

    if jobs:
        # 2. Filtrar duplicados contra DynamoDB
        jobs_nuevos = filtrar_nuevos(jobs)
        jobs_nuevos_count = len(jobs_nuevos)
        print(f"[handler] {jobs_nuevos_count} jobs nuevos (no vistos antes)")

        if jobs_nuevos:
            # 3. Filtrar por relevancia con IA
            jobs_relevantes, jobs_evaluados = filtrar_con_ia(jobs_nuevos)
            jobs_evaluados_count = len(jobs_evaluados)
            jobs_notificados_count = len(jobs_relevantes)

            # 4. Notificar resultado
            if jobs_relevantes:
                notificar(jobs_relevantes)
            elif jobs_evaluados:
                # La IA evaluó jobs pero ninguno matcheó — notificar por corrida
                notificar_sin_matches(jobs_evaluados_count)

            # 5. Guardar como vistos solo los evaluados exitosamente
            if jobs_evaluados:
                guardar_batch([job["id"] for job in jobs_evaluados])
    else:
        print("[handler] Sin resultados de Jsearch")

    # 6. Heartbeat diario — solo si no hubo nada que evaluar en todo el día
    if jobs_evaluados_count == 0 and not heartbeat_enviado_hoy():
        notificar_heartbeat({"encontrados": jobs_encontrados})
        guardar_heartbeat()

    resultado = {"procesados": jobs_evaluados_count, "notificados": jobs_notificados_count}
    print(f"[handler] Finalizado: {resultado}")
    return resultado
