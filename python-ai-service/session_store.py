"""session_store.py – abstraction layer for persisting SessionInfo.

Two implementations:
1. InMemorySessionStore – default for local/dev.
2. WordPressSessionStore – uses WP ajax endpoints (logic migrated from
   legacy ai_agent helper methods).
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Dict, List

import requests

from models import SessionInfo, ChatMessage, MessageRole

logger = logging.getLogger(__name__)


class BaseSessionStore:
    """Interface other components depend on."""

    def load(self, session_id: str) -> SessionInfo | None:  # pragma: no cover
        raise NotImplementedError

    def save(self, session: SessionInfo) -> None:  # pragma: no cover
        raise NotImplementedError


class InMemorySessionStore(BaseSessionStore):
    """Simple dict-based store for dev / unit-tests."""

    def __init__(self) -> None:
        self._store: Dict[str, SessionInfo] = {}

    def load(self, session_id: str) -> SessionInfo | None:
        return self._store.get(session_id)

    def save(self, session: SessionInfo) -> None:
        self._store[session.session_id] = session


class WordPressSessionStore(BaseSessionStore):
    """Persists session history via WP AJAX endpoints."""

    def __init__(self, wp_url: str, api_key: str):
        self._ajax_url = f"{wp_url}/wp-admin/admin-ajax.php"
        self._api_key = api_key

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _get_nonce(self) -> str:
        try:
            resp = requests.get(
                self._ajax_url,
                params={"action": "dehum_get_nonce"},
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=5,
            )
            if resp.status_code == 200 and resp.json().get("success"):
                return resp.json()["data"]["nonce"]
        except requests.RequestException as e:
            logger.debug("WP nonce error: %s", e)
        return "fallback_nonce"

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------

    def load(self, session_id: str) -> SessionInfo | None:
        nonce = self._get_nonce()
        try:
            resp = requests.post(
                self._ajax_url,
                data={"action": "dehum_get_session", "session_id": session_id, "nonce": nonce},
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=5,
            )
            if resp.status_code == 200 and resp.json().get("success"):
                history_data: List[Dict] = resp.json()["data"]["history"]
                history = [ChatMessage(**msg) for msg in history_data]
                return SessionInfo(
                    session_id=session_id,
                    conversation_history=history,
                    created_at=datetime.now(),
                    last_activity=datetime.now(),
                    message_count=len(history),
                )
        except requests.RequestException as e:
            logger.debug("WP load error: %s", e)
        return None

    def save(self, session: SessionInfo) -> None:
        nonce = self._get_nonce()
        wp_history = []
        for msg in session.conversation_history:
            if msg.role == MessageRole.USER:
                wp_history.append({"message": msg.content, "response": "", "user_ip": "", "timestamp": msg.timestamp.isoformat()})
            else:
                wp_history.append({"message": "", "response": msg.content, "user_ip": "", "timestamp": msg.timestamp.isoformat()})
        try:
            requests.post(
                self._ajax_url,
                data={
                    "action": "dehum_save_session",
                    "session_id": session.session_id,
                    "history": json.dumps(wp_history),
                    "nonce": nonce,
                },
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=5,
            )
        except requests.RequestException as e:
            logger.debug("WP save error: %s", e) 