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
        "parse_mode": "Markdown",
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
        f"{i}. *{job['titulo']}* — {job['empresa']} ({ubicacion})",
    ]
    if razon:
        lineas.append(f"   _{razon}_")
    if url:
        lineas.append(f"   [Aplicar]({url})")
    return "\n".join(lineas)


def _mensaje_detalle(jobs: list[dict]) -> str:
    n = len(jobs)
    header = f"🔔 *{n} nuevo{'s' if n > 1 else ''} job{'s' if n > 1 else ''} encontrado{'s' if n > 1 else ''}*\n"
    cuerpo = "\n\n".join(_formatear_job(i + 1, job) for i, job in enumerate(jobs))
    return header + "\n" + cuerpo


def _mensaje_resumen(jobs: list[dict]) -> str:
    n = len(jobs)
    header = f"🔔 *{n} nuevos jobs encontrados* — resumen:\n"
    lineas = []
    for job in jobs:
        ubicacion = job.get("ubicacion", "N/A")
        url = job.get("url", "")
        if url:
            lineas.append(f"• [{job['titulo']} — {job['empresa']} ({ubicacion})]({url})")
        else:
            lineas.append(f"• *{job['titulo']}* — {job['empresa']} ({ubicacion})")
    return header + "\n".join(lineas)


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
