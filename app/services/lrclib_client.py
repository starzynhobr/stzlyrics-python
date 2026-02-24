from __future__ import annotations

import logging
import re
import random
import time
import unicodedata
from dataclasses import dataclass
from http.client import RemoteDisconnected
from threading import Event
from typing import Any, Callable

import requests
from requests.adapters import HTTPAdapter


logger = logging.getLogger("stzlyrics_overlay.lrclib")

OUTCOME_SUCCESS_SYNCED = "SUCCESS_SYNCED"
OUTCOME_SUCCESS_NO_SYNCED = "SUCCESS_NO_SYNCED"
OUTCOME_FAIL_TRANSIENT_NETWORK = "FAIL_TRANSIENT_NETWORK"
OUTCOME_FAIL_PERMANENT = "FAIL_PERMANENT"


def _normalize_spaces(value: str) -> str:
    return " ".join((value or "").strip().split())


def normalize_for_match(value: str) -> str:
    value = _normalize_spaces(value).lower()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^\w\s]", "", value, flags=re.UNICODE)
    return _normalize_spaces(value)


def is_likely_match(a: str, b: str) -> bool:
    if not a or not b:
        return False
    if a == b:
        return True
    return a in b or b in a


@dataclass(slots=True)
class LrclibResult:
    found: bool
    lyrics_text: str = ""
    is_synced: bool = False
    message: str = ""
    artist: str = ""
    title: str = ""
    attempts: int = 0
    transient_error: bool = False
    error_code: str = ""
    outcome: str = OUTCOME_FAIL_PERMANENT


class LrclibClient:
    SEARCH_URL = "https://lrclib.net/api/search"

    def __init__(
        self,
        timeout_connect: float = 4.0,
        timeout_read: float = 8.0,
        max_retries: int = 2,
        backoff_base_seconds: float = 0.6,
        session: requests.Session | None = None,
    ) -> None:
        self.timeout = (timeout_connect, timeout_read)
        self.max_retries = max(0, int(max_retries))
        self.backoff_base_seconds = max(0.1, float(backoff_base_seconds))
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": "STZLyricsOverlay/1.0"})
        adapter = HTTPAdapter(pool_connections=4, pool_maxsize=4, max_retries=0)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def search(
        self,
        artist: str,
        title: str,
        *,
        progress_callback: Callable[[str, int, int, str | None], None] | None = None,
        cancel_event: Event | None = None,
    ) -> LrclibResult:
        call_started = time.perf_counter()
        params = {"artist_name": artist, "track_name": title}
        last_error: str | None = None
        last_error_code = ""
        transient_error = False
        total_attempts = self.max_retries + 1
        connect_timeout = max(0.5, float(self.timeout[0]))
        read_timeout = max(20.0, float(self.timeout[1]))
        effective_timeout = (connect_timeout, read_timeout)
        logger.info(
            "LRCLib search start artist=%r title=%r attempts=%s timeout=%s",
            artist,
            title,
            total_attempts,
            effective_timeout,
        )

        for attempt in range(total_attempts):
            if cancel_event and cancel_event.is_set():
                return LrclibResult(
                    found=False,
                    message="Cancelado",
                    attempts=attempt,
                    transient_error=True,
                    error_code="cancelled",
                    outcome=OUTCOME_FAIL_TRANSIENT_NETWORK,
                )
            attempt_number = attempt + 1
            if progress_callback is not None:
                try:
                    progress_callback("attempt", attempt_number, total_attempts, None)
                except Exception:
                    pass
            try:
                response = self.session.get(
                    self.SEARCH_URL,
                    params=params,
                    timeout=effective_timeout,
                )
                logger.info(
                    "LRCLib response attempt=%s/%s status=%s url=%s elapsed_ms=%s",
                    attempt_number,
                    total_attempts,
                    response.status_code,
                    getattr(response, "url", self.SEARCH_URL),
                    int((time.perf_counter() - call_started) * 1000),
                )
                if response.status_code in {502, 503, 504}:
                    raise requests.HTTPError(
                        f"HTTP {response.status_code}",
                        response=response,
                    )
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, list):
                    logger.warning("LRCLib invalid payload type=%s", type(payload).__name__)
                    return LrclibResult(
                        found=False,
                        message="Resposta inválida do serviço de letras",
                        attempts=attempt_number,
                        error_code="invalid_payload",
                        outcome=OUTCOME_FAIL_PERMANENT,
                    )
                result = self._select_best(payload, artist, title)
                result.attempts = attempt_number
                logger.info(
                    "LRCLib search done outcome=%s found=%s synced=%s attempts=%s elapsed_ms=%s",
                    result.outcome,
                    result.found,
                    result.is_synced,
                    attempt_number,
                    int((time.perf_counter() - call_started) * 1000),
                )
                return result
            except Exception as exc:
                error_code, friendly_message, is_retryable = self._classify_error(exc)
                logger.warning(
                    "LRCLib exception attempt=%s/%s type=%s code=%s retryable=%s msg=%s elapsed_ms=%s",
                    attempt_number,
                    total_attempts,
                    type(exc).__name__,
                    error_code,
                    is_retryable,
                    friendly_message,
                    int((time.perf_counter() - call_started) * 1000),
                )
                last_error = friendly_message
                last_error_code = error_code
                transient_error = is_retryable
                if progress_callback is not None and is_retryable and attempt < self.max_retries:
                    try:
                        progress_callback("retry", attempt_number, total_attempts, friendly_message)
                    except Exception:
                        pass
                if attempt >= self.max_retries or not is_retryable:
                    break
                logger.warning(
                    "LRCLib transient failure attempt=%s/%s type=%s code=%s msg=%s elapsed_ms=%s",
                    attempt_number,
                    total_attempts,
                    type(exc).__name__,
                    error_code,
                    friendly_message,
                    int((time.perf_counter() - call_started) * 1000),
                )
                jitter = random.uniform(0.05, 0.35)
                sleep_for = (self.backoff_base_seconds * (2**attempt)) + jitter
                if cancel_event:
                    if cancel_event.wait(timeout=sleep_for):
                        return LrclibResult(
                            found=False,
                            message="Cancelado",
                            attempts=attempt_number,
                            transient_error=True,
                            error_code="cancelled",
                            outcome=OUTCOME_FAIL_TRANSIENT_NETWORK,
                        )
                else:
                    time.sleep(sleep_for)
        if progress_callback is not None:
            try:
                progress_callback("final_error", total_attempts, total_attempts, last_error)
            except Exception:
                pass
        logger.warning(
            "LRCLib search failed outcome=%s code=%s attempts=%s elapsed_ms=%s msg=%s",
            OUTCOME_FAIL_TRANSIENT_NETWORK if transient_error else OUTCOME_FAIL_PERMANENT,
            last_error_code,
            total_attempts,
            int((time.perf_counter() - call_started) * 1000),
            last_error or "Falha temporária ao buscar letra",
        )
        return LrclibResult(
            found=False,
            message=last_error or "Falha temporária ao buscar letra",
            attempts=total_attempts,
            transient_error=transient_error,
            error_code=last_error_code,
            outcome=OUTCOME_FAIL_TRANSIENT_NETWORK if transient_error else OUTCOME_FAIL_PERMANENT,
        )

    def _classify_error(self, exc: Exception) -> tuple[str, str, bool]:
        if isinstance(exc, requests.HTTPError):
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status in {502, 503, 504}:
                return "http_5xx", "Falha temporária ao conectar no LRCLib", True
            if status == 404:
                return "http_404", "Letra não encontrada", False
            return "http_error", "Erro ao consultar serviço de letras", False
        if isinstance(exc, requests.ReadTimeout):
            return "read_timeout", "Tempo de resposta esgotado", True
        if isinstance(exc, requests.ConnectTimeout):
            return "connect_timeout", "Tempo de conexão esgotado", True
        if isinstance(exc, requests.ConnectionError):
            inner = exc.__cause__ or (exc.args[0] if exc.args else None)
            if isinstance(inner, RemoteDisconnected) or "RemoteDisconnected" in str(exc):
                return "remote_disconnected", "Conexão encerrada pelo servidor", True
            return "connection_error", "Falha de conexão temporária", True
        if isinstance(exc, requests.RequestException):
            return "request_error", "Falha temporária ao buscar letra", True
        return "unexpected_error", "Erro inesperado ao buscar letra", False

    def _select_best(self, items: list[Any], artist: str, title: str) -> LrclibResult:
        logger.info("LRCLib items received count=%s artist=%r title=%r", len(items), artist, title)
        if not items:
            return LrclibResult(found=False, message="Letra não encontrada", outcome=OUTCOME_FAIL_PERMANENT)

        expected_artist = normalize_for_match(artist)
        expected_title = normalize_for_match(title)

        best_synced: tuple[int, dict[str, Any]] | None = None
        best_plain: tuple[int, dict[str, Any]] | None = None

        for raw in items:
            if not isinstance(raw, dict):
                continue
            raw_artist = str(raw.get("artistName", ""))
            raw_title = str(raw.get("trackName", ""))
            artist_score = 2 if normalize_for_match(raw_artist) == expected_artist else 1 if is_likely_match(normalize_for_match(raw_artist), expected_artist) else 0
            title_score = 2 if normalize_for_match(raw_title) == expected_title else 1 if is_likely_match(normalize_for_match(raw_title), expected_title) else 0
            score = (artist_score * 3) + (title_score * 4)
            if score <= 0:
                continue

            synced = raw.get("syncedLyrics")
            plain = raw.get("plainLyrics")

            if isinstance(synced, str) and synced.strip():
                if best_synced is None or score > best_synced[0]:
                    best_synced = (score, raw)
            if isinstance(plain, str) and plain.strip():
                if best_plain is None or score > best_plain[0]:
                    best_plain = (score, raw)

        chosen = best_synced[1] if best_synced else (best_plain[1] if best_plain else None)
        if chosen is None:
            # Lua behavior fallback: prefer first item if no decent string match.
            for raw in items:
                if isinstance(raw, dict):
                    if isinstance(raw.get("syncedLyrics"), str) and str(raw.get("syncedLyrics")).strip():
                        chosen = raw
                        break
            if chosen is None:
                for raw in items:
                    if isinstance(raw, dict):
                        if isinstance(raw.get("plainLyrics"), str) and str(raw.get("plainLyrics")).strip():
                            chosen = raw
                            break
        if chosen is None:
            logger.info("LRCLib best match not found after scoring/fallback")
            return LrclibResult(found=False, message="Letra não encontrada", outcome=OUTCOME_FAIL_PERMANENT)

        synced_lyrics = chosen.get("syncedLyrics")
        plain_lyrics = chosen.get("plainLyrics")
        chosen_artist = str(chosen.get("artistName", artist))
        chosen_title = str(chosen.get("trackName", title))

        if isinstance(synced_lyrics, str) and synced_lyrics.strip():
            logger.info(
                "LRCLib best choice synced=yes plain=%s synced_len=%s",
                bool(isinstance(plain_lyrics, str) and plain_lyrics.strip()),
                len(synced_lyrics),
            )
            return LrclibResult(
                found=True,
                lyrics_text=synced_lyrics,
                is_synced=True,
                message="OK",
                artist=chosen_artist,
                title=chosen_title,
                outcome=OUTCOME_SUCCESS_SYNCED,
            )
        if isinstance(plain_lyrics, str) and plain_lyrics.strip():
            logger.info("LRCLib best choice synced=no plain=yes plain_len=%s", len(plain_lyrics))
            return LrclibResult(
                found=True,
                lyrics_text=plain_lyrics,
                is_synced=False,
                message="Letra sem sincronização",
                artist=chosen_artist,
                title=chosen_title,
                outcome=OUTCOME_SUCCESS_NO_SYNCED,
            )
        logger.info("LRCLib best choice has no usable lyrics fields")
        return LrclibResult(found=False, message="Letra não encontrada", outcome=OUTCOME_FAIL_PERMANENT)
