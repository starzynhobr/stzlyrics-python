from __future__ import annotations

import argparse
import inspect
import os
import sys

from PySide6.QtWidgets import QApplication

from app.config import AppPaths, load_config
from app.controller import AppController
from app.logging_utils import setup_logging
from app.services.cache import LyricsCache
from app.services.lrclib_client import LrclibClient
from app.services.media_session import MediaSessionService
from app.ui.overlay_window import OverlayWindow
from app.ui.system_tray import TrayController


def _parse_args(argv: list[str]) -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(prog="stzlyrics-overlay")
    parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="Habilita logs de diagnóstico (DEBUG).",
    )
    return parser.parse_known_args(argv)


def main() -> int:
    args, qt_args = _parse_args(sys.argv[1:])
    app = QApplication([sys.argv[0], *qt_args])
    app.setQuitOnLastWindowClosed(False)

    paths = AppPaths.default()
    paths.ensure()
    config = load_config(paths)
    logger = setup_logging(paths.logs_dir, debug=args.debug)
    logger.info("runtime_audit sys.executable=%s", sys.executable)
    logger.info("runtime_audit app.main.__file__=%s", os.path.abspath(__file__))
    logger.info("runtime_audit sys.path[0:5]=%s", sys.path[:5])
    logger.info("runtime_audit AppController.__module__=%s", AppController.__module__)
    logger.info("runtime_audit inspect.getfile(AppController)=%s", inspect.getfile(AppController))

    overlay = OverlayWindow(config=config)
    tray = TrayController()
    media_service = MediaSessionService(poll_interval_ms=config.lyrics.update_interval_ms)
    lyrics_cache = LyricsCache(
        cache_dir=paths.cache_dir,
        index_file=paths.cache_index_file,
        max_entries=config.cache.max_entries,
    )
    lrclib_client = LrclibClient(
        timeout_connect=config.network.lrclib_timeout_connect,
        timeout_read=config.network.lrclib_timeout_read,
        max_retries=config.network.lrclib_max_retries,
        backoff_base_seconds=config.network.lrclib_backoff_base_seconds,
    )

    controller = AppController(
        config=config,
        paths=paths,
        logger=logger,
        overlay=overlay,
        tray=tray,
        media_service=media_service,
        lyrics_cache=lyrics_cache,
        lrclib_client=lrclib_client,
    )
    app.aboutToQuit.connect(controller.shutdown)
    controller.start()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
