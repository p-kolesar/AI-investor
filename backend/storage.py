import json
import os

from azure.storage.blob import BlobServiceClient, ContentSettings

_conn_str = os.environ["STORAGE_CONNECTION_STRING"]


def _client(container: str, blob: str):
    return BlobServiceClient.from_connection_string(_conn_str).get_blob_client(container, blob)


def blob_read(container: str, blob: str):
    try:
        return json.loads(_client(container, blob).download_blob().readall())
    except Exception:
        return None


def blob_write(container: str, blob: str, data) -> None:
    _client(container, blob).upload_blob(json.dumps(data), overwrite=True)


def blob_write_bytes(container: str, blob: str, data: bytes, content_type: str = "application/octet-stream") -> None:
    _client(container, blob).upload_blob(
        data,
        overwrite=True,
        content_settings=ContentSettings(content_type=content_type),
    )
