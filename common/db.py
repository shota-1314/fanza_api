import os
import psycopg
from psycopg.rows import dict_row
from typing import Any, List, Dict

GenericObject = Dict[str, Any]

class Database:
    _instance = None

    def __init__(self):
        try:
            self.db_connection = psycopg.connect(
                user=os.getenv("DB_USER"),
                host=os.getenv("DB_HOST"),
                dbname=os.getenv("DB_NAME"),
                password=os.getenv("DB_PASSWORD"),
                port=int(os.getenv("DB_PORT", "5432")),
                row_factory=dict_row
            )
            self.db_connection.autocommit = False
            print(f"DB接続成功")
        except Exception as e:
            print(f"DB接続失敗", e)
            raise

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = Database()
        return cls._instance

    def start_transaction(self):
        try:
            with self.db_connection.cursor() as cur:
                cur.execute("BEGIN")
        except Exception as e:
            print(f"トランザクション開始失敗", e)
            raise

    def commit(self):
        try:
            self.db_connection.commit()
        except Exception as e:
            print(f"トランザクションコミット失敗", e)
            raise

    def rollback(self):
        try:
            self.db_connection.rollback()
        except Exception as e:
            print(f"トランザクションロールバック失敗", e)
            raise

    def query(self, sql: str, params: List[Any] = []) -> List[GenericObject]:
        try:
            with self.db_connection.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchall()
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
            with self.db_connection.cursor() as cur:
                cur.execute(sql, params)
                return
        except Exception as e:
            print(f"INSERT実行に失敗しました: {e}")
            self.rollback()
            raise