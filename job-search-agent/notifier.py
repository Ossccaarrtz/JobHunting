import os
import requests

TELEGRAM_URL = "https://api.telegram.org/bot{token}/sendMessage"
MAX_JOBS_DETALLE = 5


def _send(text: str) -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        response = requests.post(
            TELEGRAM_URL.format(token=token), json=payload, timeout=10
        )
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"[notifier] Error enviando mensaje a Telegram: {e}")


def _formatear_job(i: int, job: dict) -> str:
    ubicacion = job.get("ubicacion", "N/A")
    razon = job.get("razon_match", "")
    url = job.get("url", "")
    lineas = [
        f"{i}. <b>{job['titulo']}</b> — {job['empresa']} ({ubicacion})",
    ]
    if razon:
        lineas.append(f"   <i>{razon}</i>")
    if url:
        lineas.append(f"   <a href=\"{url}\">Aplicar</a>")
    return "\n".join(lineas)


def _mensaje_detalle(jobs: list[dict]) -> str:
    n = len(jobs)
    header = f"🔔 <b>{n} nuevo{'s' if n > 1 else ''} job{'s' if n > 1 else ''} encontrado{'s' if n > 1 else ''}</b>\n"
    cuerpo = "\n\n".join(_formatear_job(i + 1, job) for i, job in enumerate(jobs))
    return header + "\n" + cuerpo


def _mensaje_resumen(jobs: list[dict]) -> str:
    n = len(jobs)
    header = f"🔔 <b>{n} nuevos jobs encontrados</b> — resumen:\n"
    lineas = []
    for job in jobs:
        ubicacion = job.get("ubicacion", "N/A")
        url = job.get("url", "")
        if url:
            lineas.append(f"• <a href=\"{url}\">{job['titulo']} — {job['empresa']} ({ubicacion})</a>")
        else:
            lineas.append(f"• <b>{job['titulo']}</b> — {job['empresa']} ({ubicacion})")
    return header + "\n".join(lineas)


def notificar_sin_matches(evaluados: int) -> None:
    """Notifica cuando la IA evaluó jobs pero ninguno hizo match."""
    mensaje = (
        f"Lo siento Oscar, revisé {evaluados} job{'s' if evaluados != 1 else ''} "
        f"y ninguno matchea tu perfil por ahora. Seguimos buscando!"
    )
    _send(mensaje)
    print("[notifier] Notificado: sin matches")


def notificar_heartbeat(stats: dict) -> None:
    """Envía resumen diario a Telegram cuando no hubo actividad."""
    encontrados = stats.get("encontrados", 0)
    mensaje = (
        "📡 <b>Job Search Agent — activo</b>\n"
        f"<i>Sin jobs nuevos para revisar hoy ({encontrados} encontrados ya vistos).</i>"
    )
    _send(mensaje)
    print("[notifier] Heartbeat diario enviado")


def notificar(jobs: list[dict]) -> None:
    """
    Envía los jobs a Telegram.
    Si son 5 o menos: mensaje detallado por job.
    Si son más de 5: resumen en lista compacta.
    """
    if not jobs:
        return

    if len(jobs) <= MAX_JOBS_DETALLE:
        mensaje = _mensaje_detalle(jobs)
    else:
        mensaje = _mensaje_resumen(jobs)

    _send(mensaje)
    print(f"[notifier] Notificados {len(jobs)} jobs a Telegram")
