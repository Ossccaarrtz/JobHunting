import os
import time
import boto3
from botocore.exceptions import ClientError

TABLE_NAME = os.environ["DYNAMODB_TABLE"]
TTL_DAYS = 30

_dynamodb = None


def _get_table():
    global _dynamodb
    if _dynamodb is None:
        region = os.environ.get("AWS_REGION", "us-east-1")
        _dynamodb = boto3.resource("dynamodb", region_name=region)
    return _dynamodb.Table(TABLE_NAME)


def existe(job_id: str) -> bool:
    """Retorna True si el job ya fue visto anteriormente."""
    try:
        response = _get_table().get_item(Key={"job_id": job_id})
        return "Item" in response
    except ClientError as e:
        print(f"[storage] Error al consultar DynamoDB: {e}")
        return False


def guardar(job_id: str) -> None:
    """Guarda el job_id con TTL de 30 días para auto-limpieza."""
    expires_at = int(time.time()) + TTL_DAYS * 24 * 60 * 60
    try:
        _get_table().put_item(Item={"job_id": job_id, "expires_at": expires_at})
    except ClientError as e:
        print(f"[storage] Error al guardar en DynamoDB: {e}")


def guardar_batch(job_ids: list[str]) -> None:
    """Guarda múltiples job_ids en batch para reducir llamadas a DynamoDB."""
    expires_at = int(time.time()) + TTL_DAYS * 24 * 60 * 60
    table = _get_table()
    try:
        with table.batch_writer() as batch:
            for job_id in job_ids:
                batch.put_item(Item={"job_id": job_id, "expires_at": expires_at})
    except ClientError as e:
        print(f"[storage] Error en batch write: {e}")


def filtrar_nuevos(jobs: list[dict]) -> list[dict]:
    """Recibe lista de jobs y retorna solo los que no han sido vistos."""
    return [job for job in jobs if not existe(job["id"])]


def heartbeat_enviado_hoy() -> bool:
    """Retorna True si ya se envió el heartbeat diario."""
    from datetime import datetime, timezone
    hoy = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return existe(f"heartbeat_{hoy}")


def guardar_heartbeat() -> None:
    """Marca el heartbeat de hoy como enviado (TTL 2 días)."""
    from datetime import datetime, timezone
    hoy = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    expires_at = int(time.time()) + 2 * 24 * 60 * 60
    try:
        _get_table().put_item(Item={"job_id": f"heartbeat_{hoy}", "expires_at": expires_at})
    except ClientError as e:
        print(f"[storage] Error guardando heartbeat: {e}")
