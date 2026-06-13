import os
import time
import importlib
import psycopg
from psycopg.rows import dict_row
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence
from dotenv import load_dotenv

load_dotenv()

GenericObject = Dict[str, Any]
QueryParams = Sequence[Any] | Mapping[str, Any]
_ssh_tunnel = None


def _db_query_logging_enabled() -> bool:
    return os.getenv("DB_LOG_QUERIES", "true").strip().lower() in ("1", "true", "yes")


def _params_summary(params: QueryParams | None) -> str:
    if params is None:
        return "なし"
    if isinstance(params, Mapping):
        return f"keys={list(params.keys())}"
    return f"count={len(params)}"


def _db_sslmode() -> str | None:
    db_ssl = os.getenv("DB_SSL", "false").strip().lower()
    if db_ssl in ("1", "true", "yes", "require"):
        return "require"
    return None


def _ssh_env(name: str, fallback_name: str | None = None, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value:
        return value
    if fallback_name:
        value = os.getenv(fallback_name)
        if value:
            return value
    return default


def _ssh_key_path() -> str | None:
    key_path = _ssh_env("DB_SSH_KEY_PATH", "VPS_SSH_KEY_PATH")
    if not key_path:
        return None
    return os.path.expandvars(os.path.expanduser(key_path.strip().strip('"')))


def _should_use_ssh_tunnel() -> bool:
    mode = os.getenv("DB_SSH_TUNNEL", "auto").strip().lower()
    if mode in ("1", "true", "yes", "require"):
        return True
    if mode in ("0", "false", "no", "disable", "disabled"):
        return False

    ssh_host = _ssh_env("DB_SSH_HOST", "VPS_HOST")
    key_path = _ssh_key_path()
    if ssh_host and key_path and Path(key_path).is_file():
        print(f"SSH鍵を検出したためSSHトンネル経由でDB接続します: {key_path}")
        return True

    print("SSH鍵が見つからないため、DBへ直接接続します")
    return False


def _connection_kwargs() -> dict:
    host = os.getenv("DB_HOST", "127.0.0.1")
    port = int(os.getenv("DB_PORT", "5432"))

    if _should_use_ssh_tunnel():
        host, port = _start_ssh_tunnel()

    kwargs = {
        "user": os.getenv("DB_USER"),
        "host": host,
        "dbname": os.getenv("DB_NAME"),
        "password": os.getenv("DB_PASSWORD"),
        "port": port,
        "row_factory": dict_row,
        "connect_timeout": int(os.getenv("DB_CONNECT_TIMEOUT", "10")),
    }
    sslmode = _db_sslmode()
    if sslmode:
        kwargs["sslmode"] = sslmode
    return kwargs


def _start_ssh_tunnel() -> tuple[str, int]:
    global _ssh_tunnel
    if _ssh_tunnel is not None and _ssh_tunnel.is_active:
        return "127.0.0.1", _ssh_tunnel.local_bind_port

    try:
        sshtunnel = importlib.import_module("sshtunnel")
        SSHTunnelForwarder = sshtunnel.SSHTunnelForwarder
    except ImportError as e:
        import sys
        print(f"ImportError details: {e}")
        print(f"sys.path: {sys.path}")
        print(f"sys.executable: {sys.executable}")
        raise RuntimeError("SSH tunnel requires `sshtunnel`. Run `pip install sshtunnel`.") from e

    ssh_host = _ssh_env("DB_SSH_HOST", "VPS_HOST")
    ssh_user = _ssh_env("DB_SSH_USER", "VPS_USER", "root")
    ssh_port = int(_ssh_env("DB_SSH_PORT", "VPS_PORT", "22"))
    ssh_key_path = _ssh_key_path()
    remote_host = os.getenv("DB_SSH_REMOTE_HOST", "127.0.0.1")
    remote_port = int(os.getenv("DB_SSH_REMOTE_PORT", os.getenv("DB_PORT", "5432")))

    if not ssh_host:
        raise RuntimeError("DB_SSH_HOST or VPS_HOST is required when SSH tunnel is enabled")
    if not ssh_key_path:
        raise RuntimeError("DB_SSH_KEY_PATH or VPS_SSH_KEY_PATH is required when SSH tunnel is enabled")
    if not Path(ssh_key_path).is_file():
        raise RuntimeError(f"SSH key file was not found: {ssh_key_path}")

    try:
        _ssh_tunnel = SSHTunnelForwarder(
            (ssh_host, ssh_port),
            ssh_username=ssh_user,
            ssh_pkey=ssh_key_path,
            remote_bind_address=(remote_host, remote_port),
            local_bind_address=("127.0.0.1", 0),
        )
        _ssh_tunnel.start()
        print(f"SSHトンネルを確立しました (ローカルポート: {_ssh_tunnel.local_bind_port})")
    except Exception as e:
        print(f"SSHトンネルの確立に失敗しました: {e}")
        raise RuntimeError(f"SSHトンネルの確立に失敗しました: {e}") from e

    return "127.0.0.1", _ssh_tunnel.local_bind_port


class Database:
    _instance = None

    def __init__(self):
        retries = int(os.getenv("DB_CONNECT_RETRIES", "3"))
        retry_delay = int(os.getenv("DB_CONNECT_RETRY_DELAY", "3"))

        for attempt in range(1, retries + 1):
            try:
                self.db_connection = psycopg.connect(**_connection_kwargs())
                self.db_connection.autocommit = False
                print("DB接続成功")
                return
            except Exception as e:
                print(f"DB接続失敗 ({attempt}/{retries})", e)
                if attempt == retries:
                    raise
                time.sleep(retry_delay)

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = Database()
        return cls._instance

    def start_transaction(self):
        try:
            if self.db_connection.closed:
                self.reconnect()

            print("トランザクション開始")
            with self.db_connection.cursor() as cur:
                cur.execute("BEGIN")
            print("トランザクション開始完了")
        except Exception as e:
            print(f"トランザクション開始失敗", e)
            error_msg = str(e).lower()
            reconnect_errors = (
                "connection is closed",
                "connection already closed",
                "ssl connection has been closed unexpectedly",
                "server closed the connection unexpectedly",
            )
            if any(message in error_msg for message in reconnect_errors):
                try:
                    self.reconnect()
                    with self.db_connection.cursor() as cur:
                        cur.execute("BEGIN")
                except Exception as retry_e:
                    print(f"トランザクション開始リトライ失敗", retry_e)
                    raise
            else:
                raise

    def reconnect(self):
        """データベースへの再接続を行う"""
        try:
            print("DB再接続を試みます...")
            try:
                if self.db_connection and not self.db_connection.closed:
                    self.db_connection.close()
            except Exception:
                pass

            self.db_connection = psycopg.connect(**_connection_kwargs())
            self.db_connection.autocommit = False
            print("DB再接続成功")
        except Exception as e:
            print(f"DB再接続失敗: {e}")
            raise

    def commit(self):
        try:
            print("トランザクションコミット開始")
            self.db_connection.commit()
            print("トランザクションコミット完了")
        except Exception as e:
            print(f"トランザクションコミット失敗", e)
            raise

    def rollback(self):
        try:
            print("トランザクションロールバック開始")
            self.db_connection.rollback()
            print("トランザクションロールバック完了")
        except Exception as e:
            print(f"トランザクションロールバック失敗", e)
            raise

    def query(self, sql: str, params: QueryParams | None = None) -> List[GenericObject]:
        try:
            started_at = time.monotonic()
            if _db_query_logging_enabled():
                print(f"SELECT実行開始: params={_params_summary(params)}")
            with self.db_connection.cursor() as cur:
                cur.execute(sql, params or [])
                rows = cur.fetchall()
            if _db_query_logging_enabled():
                elapsed = time.monotonic() - started_at
                print(f"SELECT実行完了: rows={len(rows)}, elapsed={elapsed:.3f}s")
            return rows
        except Exception as e:
            print(f"SELECT実行に失敗しました: {e}")
            self.rollback()
            raise

    def insert(self, sql: str, params: dict) -> None:
        """
        INSERT文を実行する。

        Parameters
        ----------
        sql : str
            実行するINSERT文（%()s形式のパラメータ埋め込み対応）
        params : dict
            パラメータ辞書（キーがカラム名）

        Raises
        ------
        Exception
            クエリ実行に失敗した場合
        """
        try:
            started_at = time.monotonic()
            if _db_query_logging_enabled():
                print(f"INSERT/UPSERT実行開始: params={_params_summary(params)}")
            with self.db_connection.cursor() as cur:
                cur.execute(sql, params)
            if _db_query_logging_enabled():
                elapsed = time.monotonic() - started_at
                print(f"INSERT/UPSERT実行完了: elapsed={elapsed:.3f}s")
                return
        except Exception as e:
            print(f"INSERT実行に失敗しました: {e}")
            self.rollback()
            raise

    def close(self):
        """データベース接続とSSHトンネルを閉じる"""
        try:
            if self.db_connection and not self.db_connection.closed:
                self.db_connection.close()
                print("DB接続を閉じました。")
        except Exception as e:
            print(f"DB接続のクローズに失敗しました: {e}")

        global _ssh_tunnel
        if _ssh_tunnel is not None and _ssh_tunnel.is_active:
            try:
                _ssh_tunnel.stop()
                print("SSHトンネルを閉じました。")
            except Exception as e:
                print(f"SSHトンネルのクローズに失敗しました: {e}")