import io
import os
from typing import List

import pandas as pd

try:
    from azure.storage.blob import BlobClient, ContainerClient
except ImportError as exc:  # pragma: no cover - dependency missing
    raise RuntimeError("azure-storage-blob is required for storage. Install it in your environment.") from exc

AZURE_CONNECTION_STRING = os.getenv("AZURE_CONNECTION_STRING")
AZURE_CONTAINER = os.getenv("AZURE_CONTAINER")

if not (AZURE_CONNECTION_STRING and AZURE_CONTAINER):
    raise RuntimeError("AZURE_CONNECTION_STRING and AZURE_CONTAINER must be set for storage access.")

HEADERS = {
    "players": ["player_id", "name", "created_at"],
    "games": ["game_id", "round_name", "player_a", "player_b", "allow_draw", "played_at"],
    "stats": [
        "game_id",
        "player_id",
        "xg",
        "xga",
        "goals",
        "dribble_success",
        "key_passes",
        "interceptions",
        "tackles",
        "result",
    ],
}


def _get_container_client() -> ContainerClient:
    try:
        return ContainerClient.from_connection_string(AZURE_CONNECTION_STRING, AZURE_CONTAINER)
    except Exception as exc:  # pragma: no cover - network/config
        raise RuntimeError(f"Cannot connect to Azure container: {exc}") from exc


def _get_blob_client(blob_name: str) -> BlobClient:
    container_client = _get_container_client()
    return container_client.get_blob_client(blob_name)


def _ensure_blob(blob_name: str, header_cols: List[str]) -> None:
    blob_client = _get_blob_client(blob_name)
    if not blob_client.exists():
        buffer = io.BytesIO()
        pd.DataFrame(columns=header_cols).to_csv(buffer, index=False)
        buffer.seek(0)
        blob_client.upload_blob(buffer.getvalue(), overwrite=True)


def _read_blob(blob_name: str, header_cols: List[str]) -> pd.DataFrame:
    blob_client = _get_blob_client(blob_name)
    if not blob_client.exists():
        return pd.DataFrame(columns=header_cols)
    data = blob_client.download_blob().readall()
    df = pd.read_csv(io.BytesIO(data))
    for col in header_cols:
        if col not in df.columns:
            df[col] = []
    return df[header_cols]


def _write_blob(blob_name: str, df: pd.DataFrame, header_cols: List[str]) -> None:
    blob_client = _get_blob_client(blob_name)
    buffer = io.BytesIO()
    df[header_cols].to_csv(buffer, index=False)
    buffer.seek(0)
    blob_client.upload_blob(buffer.getvalue(), overwrite=True)


def ensure_data_files() -> None:
    for title, cols in HEADERS.items():
        blob_name = f"{title}.csv"
        _ensure_blob(blob_name, cols)


def load_players() -> pd.DataFrame:
    return _read_blob("players.csv", HEADERS["players"])


def load_games() -> pd.DataFrame:
    return _read_blob("games.csv", HEADERS["games"])


def load_stats() -> pd.DataFrame:
    df = _read_blob("stats.csv", HEADERS["stats"])
    if "goals" not in df.columns:
        df["goals"] = 0
    return df


def save_players(df: pd.DataFrame) -> None:
    _write_blob("players.csv", df, HEADERS["players"])


def save_games(df: pd.DataFrame) -> None:
    _write_blob("games.csv", df, HEADERS["games"])


def save_stats(df: pd.DataFrame) -> None:
    _write_blob("stats.csv", df, HEADERS["stats"])


def next_id(df: pd.DataFrame, col: str, prefix: str) -> str:
    if df.empty:
        return f"{prefix}1"
    numeric_parts: List[int] = []
    for raw in df[col].astype(str):
        suffix = raw[len(prefix) :]
        numeric_parts.append(int(suffix) if suffix.isdigit() else 0)
    return f"{prefix}{max(numeric_parts) + 1}"
