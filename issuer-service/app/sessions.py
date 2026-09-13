import threading
import time
import uuid
import secrets
import ipaddress
from collections import defaultdict, deque

from . import config


class SessionExpired(Exception):
    pass


class SessionNotFound(Exception):
    pass


class RateLimited(Exception):
    pass


AVAILABLE_CHALLENGES = []          # populated at startup based on capabilities
_rate = defaultdict(deque)


def register_challenge(kind: str):
    if kind not in AVAILABLE_CHALLENGES:
        AVAILABLE_CHALLENGES.append(kind)


def check_rate(ip: str):
    now = time.time()
    q = _rate[ip]
    while q and now - q[0] > 3600:
        q.popleft()
    if len(q) >= config.RATE_LIMIT_PER_HOUR:
        raise RateLimited()
    q.append(now)


class SessionStore:
    def __init__(self):
        self._lock = threading.Lock()
        self._sessions = {}

    def create(self, challenge: dict) -> str:
        sid = uuid.uuid4().hex
        with self._lock:
            self._sessions[sid] = {
                "challenge": challenge,
                "created_at": time.time(),
            }
        return sid

    def consume(self, sid: str) -> dict:
        """One-shot: removes the session atomically. Prevents double-submit/replay."""
        with self._lock:
            sess = self._sessions.pop(sid, None)
        if sess is None:
            raise SessionNotFound()
        if time.time() - sess["created_at"] > config.SESSION_TTL_SECONDS:
            raise SessionExpired()
        return sess

    def expire_for_test(self, sid: str, delta_seconds: float):
        with self._lock:
            self._sessions[sid]["created_at"] -= delta_seconds


store = SessionStore()
