from __future__ import annotations

from typing import Any


DEFAULT_UI_LANGUAGE = "PT-BR"
APP_NAME = "STZLyrics Overlay"


UI_TEXTS: dict[str, dict[str, str]] = {
    "PT-BR": {
        "app_name": APP_NAME,
        "tray_settings": "Configurações...",
        "tray_open_cache": "Abrir pasta do cache",
        "tray_reload_config": "Recarregar config",
        "tray_quit": "Sair",
        "tray_tooltip_error": "{app_name} - {message}",
        "overlay_waiting_music": "Aguardando música...",
        "overlay_winsdk_not_installed": "winsdk não instalado",
        "overlay_no_media_active": "Nenhuma mídia ativa",
        "overlay_waiting_metadata": "Aguardando metadados...",
        "overlay_loading_lyrics": "Buscando letra...",
        "status_fetch_attempt": "Buscando letra... tentativa {attempt}/{total}",
        "status_lyrics_unavailable": "Letra indisponível",
        "overlay_lyrics_not_found": "Letra não encontrada.",
        "overlay_synced_parse_failed": "Letra indisponível.",
        "status_config_reload_failed": "Falha ao recarregar config",
        "status_config_reloaded": "Config recarregada",
        "status_config_saved": "Config salva",
        "msg_temp_lyrics_fetch_fail": "Falha temporária ao buscar letra",
        "msg_network_timeout_retrying": "Falha de rede (timeout). Tentando novamente...",
        "msg_network_transient_retrying": "Falha temporária de conexão. Tentando novamente...",
        "default_no_synced_text": "Sem letra sincronizada para esta música.",
    },
    "EN": {
        "app_name": APP_NAME,
        "tray_settings": "Settings...",
        "tray_open_cache": "Open cache folder",
        "tray_reload_config": "Reload config",
        "tray_quit": "Quit",
        "tray_tooltip_error": "{app_name} - {message}",
        "overlay_waiting_music": "Waiting for music...",
        "overlay_winsdk_not_installed": "winsdk not installed",
        "overlay_no_media_active": "No active media",
        "overlay_waiting_metadata": "Waiting for metadata...",
        "overlay_loading_lyrics": "Fetching lyrics...",
        "status_fetch_attempt": "Fetching lyrics... attempt {attempt}/{total}",
        "status_lyrics_unavailable": "Lyrics unavailable",
        "overlay_lyrics_not_found": "Lyrics not found.",
        "overlay_synced_parse_failed": "Lyrics unavailable.",
        "status_config_reload_failed": "Failed to reload config",
        "status_config_reloaded": "Config reloaded",
        "status_config_saved": "Config saved",
        "msg_temp_lyrics_fetch_fail": "Temporary failure while fetching lyrics",
        "msg_network_timeout_retrying": "Network failure (timeout). Retrying...",
        "msg_network_transient_retrying": "Temporary network failure. Retrying...",
        "default_no_synced_text": "No synchronized lyrics for this track.",
    },
    "ES": {
        "app_name": APP_NAME,
        "tray_settings": "Configuración...",
        "tray_open_cache": "Abrir carpeta de caché",
        "tray_reload_config": "Recargar config",
        "tray_quit": "Salir",
        "tray_tooltip_error": "{app_name} - {message}",
        "overlay_waiting_music": "Esperando música...",
        "overlay_winsdk_not_installed": "winsdk no instalado",
        "overlay_no_media_active": "Sin medio activo",
        "overlay_waiting_metadata": "Esperando metadatos...",
        "overlay_loading_lyrics": "Buscando letra...",
        "status_fetch_attempt": "Buscando letra... intento {attempt}/{total}",
        "status_lyrics_unavailable": "Letra no disponible",
        "overlay_lyrics_not_found": "Letra no encontrada.",
        "overlay_synced_parse_failed": "Letra no disponible.",
        "status_config_reload_failed": "Error al recargar config",
        "status_config_reloaded": "Config recargada",
        "status_config_saved": "Config guardada",
        "msg_temp_lyrics_fetch_fail": "Fallo temporal al buscar la letra",
        "msg_network_timeout_retrying": "Fallo de red (timeout). Reintentando...",
        "msg_network_transient_retrying": "Fallo temporal de red. Reintentando...",
        "default_no_synced_text": "No hay letra sincronizada para esta canción.",
    },
    "IT": {
        "app_name": APP_NAME,
        "tray_settings": "Impostazioni...",
        "tray_open_cache": "Apri cartella cache",
        "tray_reload_config": "Ricarica config",
        "tray_quit": "Esci",
        "tray_tooltip_error": "{app_name} - {message}",
        "overlay_waiting_music": "In attesa della musica...",
        "overlay_winsdk_not_installed": "winsdk non installato",
        "overlay_no_media_active": "Nessun contenuto attivo",
        "overlay_waiting_metadata": "In attesa dei metadati...",
        "overlay_loading_lyrics": "Ricerca testo...",
        "status_fetch_attempt": "Ricerca testo... tentativo {attempt}/{total}",
        "status_lyrics_unavailable": "Testo non disponibile",
        "overlay_lyrics_not_found": "Testo non trovato.",
        "overlay_synced_parse_failed": "Testo non disponibile.",
        "status_config_reload_failed": "Errore nel ricaricare config",
        "status_config_reloaded": "Config ricaricata",
        "status_config_saved": "Config salvata",
        "msg_temp_lyrics_fetch_fail": "Errore temporaneo durante la ricerca del testo",
        "msg_network_timeout_retrying": "Errore di rete (timeout). Riprovo...",
        "msg_network_transient_retrying": "Errore di rete temporaneo. Riprovo...",
        "default_no_synced_text": "Nessun testo sincronizzato per questo brano.",
    },
    "DE": {
        "app_name": APP_NAME,
        "tray_settings": "Einstellungen...",
        "tray_open_cache": "Cache-Ordner öffnen",
        "tray_reload_config": "Config neu laden",
        "tray_quit": "Beenden",
        "tray_tooltip_error": "{app_name} - {message}",
        "overlay_waiting_music": "Warte auf Musik...",
        "overlay_winsdk_not_installed": "winsdk nicht installiert",
        "overlay_no_media_active": "Kein aktives Medium",
        "overlay_waiting_metadata": "Warte auf Metadaten...",
        "overlay_loading_lyrics": "Liedtext wird geladen...",
        "status_fetch_attempt": "Liedtext wird geladen... Versuch {attempt}/{total}",
        "status_lyrics_unavailable": "Liedtext nicht verfügbar",
        "overlay_lyrics_not_found": "Liedtext nicht gefunden.",
        "overlay_synced_parse_failed": "Liedtext nicht verfügbar.",
        "status_config_reload_failed": "Config konnte nicht neu geladen werden",
        "status_config_reloaded": "Config neu geladen",
        "status_config_saved": "Config gespeichert",
        "msg_temp_lyrics_fetch_fail": "Temporärer Fehler beim Laden des Liedtexts",
        "msg_network_timeout_retrying": "Netzwerkfehler (Timeout). Erneuter Versuch...",
        "msg_network_transient_retrying": "Temporärer Netzwerkfehler. Erneuter Versuch...",
        "default_no_synced_text": "Keine synchronisierten Liedtexte für diesen Titel.",
    },
    "FR": {
        "app_name": APP_NAME,
        "tray_settings": "Paramètres...",
        "tray_open_cache": "Ouvrir le dossier cache",
        "tray_reload_config": "Recharger la config",
        "tray_quit": "Quitter",
        "tray_tooltip_error": "{app_name} - {message}",
        "overlay_waiting_music": "En attente de musique...",
        "overlay_winsdk_not_installed": "winsdk non installé",
        "overlay_no_media_active": "Aucun média actif",
        "overlay_waiting_metadata": "En attente des métadonnées...",
        "overlay_loading_lyrics": "Recherche des paroles...",
        "status_fetch_attempt": "Recherche des paroles... tentative {attempt}/{total}",
        "status_lyrics_unavailable": "Paroles indisponibles",
        "overlay_lyrics_not_found": "Paroles introuvables.",
        "overlay_synced_parse_failed": "Paroles indisponibles.",
        "status_config_reload_failed": "Échec du rechargement de la config",
        "status_config_reloaded": "Config rechargée",
        "status_config_saved": "Config enregistrée",
        "msg_temp_lyrics_fetch_fail": "Échec temporaire lors de la récupération des paroles",
        "msg_network_timeout_retrying": "Erreur réseau (timeout). Nouvelle tentative...",
        "msg_network_transient_retrying": "Erreur réseau temporaire. Nouvelle tentative...",
        "default_no_synced_text": "Aucune parole synchronisée pour ce morceau.",
    },
    "JP": {
        "app_name": APP_NAME,
        "tray_settings": "設定...",
        "tray_open_cache": "キャッシュフォルダを開く",
        "tray_reload_config": "設定を再読み込み",
        "tray_quit": "終了",
        "tray_tooltip_error": "{app_name} - {message}",
        "overlay_waiting_music": "音楽を待機中...",
        "overlay_winsdk_not_installed": "winsdk がインストールされていません",
        "overlay_no_media_active": "アクティブなメディアがありません",
        "overlay_waiting_metadata": "メタデータを待機中...",
        "overlay_loading_lyrics": "歌詞を取得中...",
        "status_fetch_attempt": "歌詞を取得中... 試行 {attempt}/{total}",
        "status_lyrics_unavailable": "歌詞を利用できません",
        "overlay_lyrics_not_found": "歌詞が見つかりません。",
        "overlay_synced_parse_failed": "歌詞を利用できません。",
        "status_config_reload_failed": "設定の再読み込みに失敗しました",
        "status_config_reloaded": "設定を再読み込みしました",
        "status_config_saved": "設定を保存しました",
        "msg_temp_lyrics_fetch_fail": "歌詞取得中に一時的なエラーが発生しました",
        "msg_network_timeout_retrying": "ネットワークエラー (タイムアウト)。再試行中...",
        "msg_network_transient_retrying": "一時的なネットワークエラー。再試行中...",
        "default_no_synced_text": "この曲の同期歌詞はありません。",
    },
}


def normalize_ui_language(language_code: str | None) -> str:
    code = (language_code or "").strip().upper()
    if code in UI_TEXTS:
        return code
    if code.startswith("PT"):
        return "PT-BR"
    if code.startswith("EN"):
        return "EN"
    if code.startswith("ES"):
        return "ES"
    if code.startswith("IT"):
        return "IT"
    if code.startswith("DE"):
        return "DE"
    if code.startswith("FR"):
        return "FR"
    if code.startswith("JP") or code.startswith("JA"):
        return "JP"
    return "EN"


def tr_ui(language_code: str | None, key: str, **kwargs: Any) -> str:
    lang = normalize_ui_language(language_code)
    template = UI_TEXTS.get(lang, {}).get(key) or UI_TEXTS["EN"].get(key) or key
    if kwargs:
        try:
            return template.format(**kwargs)
        except Exception:
            return template
    return template
