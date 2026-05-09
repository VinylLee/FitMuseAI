from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sqlite3
import threading
from typing import Any, Iterable, Optional


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat()


class MetadataStore:
    def __init__(self, db_path: Path) -> None:
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS persons (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    image_path TEXT NOT NULL,
                    thumbnail_path TEXT,
                    description TEXT,
                    is_authorized INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS garments (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    image_path TEXT NOT NULL,
                    thumbnail_path TEXT,
                    category TEXT,
                    description TEXT,
                    must_preserve_logo INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS results (
                    id TEXT PRIMARY KEY,
                    person_id TEXT,
                    garment_id TEXT,
                    result_type TEXT,
                    provider TEXT,
                    model TEXT,
                    prompt TEXT,
                    negative_prompt TEXT,
                    output_path TEXT,
                    seed INTEGER,
                    status TEXT,
                    error_message TEXT,
                    is_canonical INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS canonical_images (
                    id TEXT PRIMARY KEY,
                    person_id TEXT NOT NULL,
                    garment_id TEXT NOT NULL,
                    result_id TEXT NOT NULL,
                    image_path TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(person_id, garment_id)
                )
                """
            )
            self._conn.commit()

    def _execute(self, sql: str, params: Optional[Iterable[Any]] = None) -> sqlite3.Cursor:
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute(sql, params or [])
            self._conn.commit()
            return cursor

    def add_person(self, person: dict[str, Any]) -> dict[str, Any]:
        person = dict(person)
        person.setdefault("created_at", _now_iso())
        self._execute(
            """
            INSERT INTO persons (id, name, image_path, thumbnail_path, description, is_authorized, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                person["id"],
                person["name"],
                person["image_path"],
                person.get("thumbnail_path"),
                person.get("description"),
                1 if person.get("is_authorized") else 0,
                person["created_at"],
            ],
        )
        return person

    def add_garment(self, garment: dict[str, Any]) -> dict[str, Any]:
        garment = dict(garment)
        garment.setdefault("created_at", _now_iso())
        self._execute(
            """
            INSERT INTO garments (id, name, image_path, thumbnail_path, category, description, must_preserve_logo, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                garment["id"],
                garment["name"],
                garment["image_path"],
                garment.get("thumbnail_path"),
                garment.get("category"),
                garment.get("description"),
                1 if garment.get("must_preserve_logo") else 0,
                garment["created_at"],
            ],
        )
        return garment

    def list_persons(self) -> list[dict[str, Any]]:
        cursor = self._execute("SELECT * FROM persons ORDER BY created_at DESC")
        return [dict(row) for row in cursor.fetchall()]

    def list_garments(self) -> list[dict[str, Any]]:
        cursor = self._execute("SELECT * FROM garments ORDER BY created_at DESC")
        return [dict(row) for row in cursor.fetchall()]

    def get_person(self, person_id: str) -> Optional[dict[str, Any]]:
        cursor = self._execute("SELECT * FROM persons WHERE id = ?", [person_id])
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_garment(self, garment_id: str) -> Optional[dict[str, Any]]:
        cursor = self._execute("SELECT * FROM garments WHERE id = ?", [garment_id])
        row = cursor.fetchone()
        return dict(row) if row else None

    def update_person(
        self,
        person_id: str,
        name: str,
        description: Optional[str],
        is_authorized: bool,
    ) -> bool:
        cursor = self._execute(
            "UPDATE persons SET name = ?, description = ?, is_authorized = ? WHERE id = ?",
            [name, description, 1 if is_authorized else 0, person_id],
        )
        return cursor.rowcount > 0

    def update_garment(
        self,
        garment_id: str,
        name: str,
        category: Optional[str],
        description: Optional[str],
        must_preserve_logo: bool,
    ) -> bool:
        cursor = self._execute(
            "UPDATE garments SET name = ?, category = ?, description = ?, must_preserve_logo = ? WHERE id = ?",
            [name, category, description, 1 if must_preserve_logo else 0, garment_id],
        )
        return cursor.rowcount > 0

    def delete_person(self, person_id: str) -> None:
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("DELETE FROM canonical_images WHERE person_id = ?", [person_id])
            cursor.execute("DELETE FROM results WHERE person_id = ?", [person_id])
            cursor.execute("DELETE FROM persons WHERE id = ?", [person_id])
            self._conn.commit()

    def delete_garment(self, garment_id: str) -> None:
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("DELETE FROM canonical_images WHERE garment_id = ?", [garment_id])
            cursor.execute("DELETE FROM results WHERE garment_id = ?", [garment_id])
            cursor.execute("DELETE FROM garments WHERE id = ?", [garment_id])
            self._conn.commit()

    def add_results(self, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not results:
            return []

        prepared = []
        for result in results:
            result = dict(result)
            result.setdefault("created_at", _now_iso())
            prepared.append(
                [
                    result["id"],
                    result.get("person_id"),
                    result.get("garment_id"),
                    result.get("result_type"),
                    result.get("provider"),
                    result.get("model"),
                    result.get("prompt"),
                    result.get("negative_prompt"),
                    result.get("output_path"),
                    result.get("seed"),
                    result.get("status"),
                    result.get("error_message"),
                    1 if result.get("is_canonical") else 0,
                    result["created_at"],
                ]
            )

        with self._lock:
            cursor = self._conn.cursor()
            cursor.executemany(
                """
                INSERT INTO results (
                    id, person_id, garment_id, result_type, provider, model, prompt,
                    negative_prompt, output_path, seed, status, error_message, is_canonical, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                prepared,
            )
            self._conn.commit()

        return results

    def list_results(
        self,
        person_id: Optional[str] = None,
        garment_id: Optional[str] = None,
        result_type: Optional[str] = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM results WHERE 1=1"
        params: list[Any] = []
        if person_id:
            sql += " AND person_id = ?"
            params.append(person_id)
        if garment_id:
            sql += " AND garment_id = ?"
            params.append(garment_id)
        if result_type and result_type != "all":
            sql += " AND result_type = ?"
            params.append(result_type)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        cursor = self._execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]

    def list_results_for_combo(self, person_id: str, garment_id: str) -> list[dict[str, Any]]:
        cursor = self._execute(
            "SELECT * FROM results WHERE person_id = ? AND garment_id = ? ORDER BY created_at DESC",
            [person_id, garment_id],
        )
        return [dict(row) for row in cursor.fetchall()]

    def set_canonical_image(self, person_id: str, garment_id: str, result_id: str) -> Optional[dict[str, Any]]:
        result = self._execute("SELECT * FROM results WHERE id = ?", [result_id]).fetchone()
        if not result:
            return None

        canonical_id = f"canonical_{person_id}_{garment_id}"
        image_path = result["output_path"] or ""
        created_at = _now_iso()

        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute(
                "UPDATE results SET is_canonical = 0 WHERE person_id = ? AND garment_id = ?",
                [person_id, garment_id],
            )
            cursor.execute("UPDATE results SET is_canonical = 1 WHERE id = ?", [result_id])
            cursor.execute(
                """
                INSERT INTO canonical_images (id, person_id, garment_id, result_id, image_path, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(person_id, garment_id)
                DO UPDATE SET result_id = excluded.result_id, image_path = excluded.image_path, created_at = excluded.created_at
                """,
                [canonical_id, person_id, garment_id, result_id, image_path, created_at],
            )
            self._conn.commit()

        return {
            "id": canonical_id,
            "person_id": person_id,
            "garment_id": garment_id,
            "result_id": result_id,
            "image_path": image_path,
            "created_at": created_at,
        }

    def get_canonical_image(self, person_id: str, garment_id: str) -> Optional[dict[str, Any]]:
        cursor = self._execute(
            "SELECT * FROM canonical_images WHERE person_id = ? AND garment_id = ?",
            [person_id, garment_id],
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def clear_canonical_image(self, person_id: str, garment_id: str) -> None:
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute(
                "UPDATE results SET is_canonical = 0 WHERE person_id = ? AND garment_id = ?",
                [person_id, garment_id],
            )
            cursor.execute(
                "DELETE FROM canonical_images WHERE person_id = ? AND garment_id = ?",
                [person_id, garment_id],
            )
            self._conn.commit()
