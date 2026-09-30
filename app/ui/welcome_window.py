from __future__ import annotations

import math

from PySide6.QtCore import QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QBoxLayout, QButtonGroup, QDialog, QFrame, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from app.config import AppConfig
from app.i18n import normalize_ui_language, tr_settings_ui
from app.layout_presets import build_layout_render_model, normalize_layout_preset
from app.ui.app_icon import load_app_icon
from app.ui.settings_window import _set_dark_windows_title_bar


_KEYS = (
    "eyebrow", "title", "description", "preview", "preview_note", "choose",
    "choose_note", "play_title", "play_body", "style_title", "style_body",
    "tray_title", "tray_body", "availability", "begin", "settings", "later", "error",
)
_COPY = {
    "PT-BR": (
        "SUA MÚSICA. MAIS PERTO.", "A letra acompanha.\nVocê aproveita.",
        "Suas letras sincronizadas sobre a área de trabalho, sem precisar trocar de janela.",
        "UMA PRÉVIA NO SEU DESKTOP", "Demonstração • funciona mesmo sem música tocando",
        "Um estilo para o seu ritmo", "Experimente a prévia. Você pode mudar depois.",
        "Dê o play", "Abra o Spotify ou outro player compatível com a mídia do Windows e toque uma música.",
        "Deixe do seu jeito", "Escolha um estilo. Ajuste cor, tamanho e posição nas configurações.",
        "Sempre por perto", "Perto do relógio, abra os ícones ocultos (^) e clique com o botão direito no STZLyrics.",
        "As letras são buscadas online no LRCLib. Algumas faixas podem não ter letra sincronizada disponível.",
        "Começar a usar", "Configurações", "Agora não", "Não foi possível salvar. Tente novamente.",
    ),
    "EN": (
        "YOUR MUSIC. A LITTLE CLOSER.", "Lyrics follow.\nYou enjoy.",
        "Synced lyrics over your desktop, without switching windows.",
        "A PREVIEW ON YOUR DESKTOP", "Demo • works even when no music is playing",
        "A style for your rhythm", "Try the preview. You can change it later.",
        "Press play", "Open Spotify or another Windows media-compatible player and play a song.",
        "Make it yours", "Choose a style. Adjust color, size and position in settings.",
        "Always nearby", "Near the clock, open hidden icons (^) and right-click STZLyrics.",
        "Lyrics are fetched online from LRCLib. Synced lyrics may not be available for every track.",
        "Get started", "Settings", "Not now", "Could not save. Please try again.",
    ),
    "ES": (
        "TU MÚSICA. MÁS CERCA.", "La letra sigue.\nTú disfrutas.",
        "Letras sincronizadas sobre tu escritorio, sin cambiar de ventana.",
        "UNA VISTA PREVIA EN TU ESCRITORIO", "Demostración • funciona sin música",
        "Un estilo para tu ritmo", "Prueba la vista previa. Puedes cambiarlo después.",
        "Dale al play", "Abre Spotify u otro reproductor compatible con los medios de Windows y reproduce una canción.",
        "A tu manera", "Elige un estilo. Ajusta el color, el tamaño y la posición en la configuración.",
        "Siempre a mano", "Junto al reloj, abre los iconos ocultos (^) y haz clic derecho en STZLyrics.",
        "Las letras se buscan en línea en LRCLib. Algunas canciones pueden no tener letras sincronizadas.",
        "Empezar", "Configuración", "Ahora no", "No se pudo guardar. Inténtalo de nuevo.",
    ),
    "IT": (
        "LA TUA MUSICA. PIÙ VICINA.", "Il testo ti segue.\nTu ascolta.",
        "Testi sincronizzati sul desktop, senza cambiare finestra.",
        "UN'ANTEPRIMA SUL DESKTOP", "Demo • funziona anche senza musica",
        "Uno stile per il tuo ritmo", "Prova l'anteprima. Puoi cambiare in seguito.",
        "Premi play", "Apri Spotify o un altro lettore compatibile con i contenuti multimediali di Windows e riproduci un brano.",
        "A modo tuo", "Scegli uno stile. Regola colore, dimensioni e posizione nelle impostazioni.",
        "Sempre a portata di mano", "Vicino all'orologio, apri le icone nascoste (^) e fai clic destro su STZLyrics.",
        "I testi vengono cercati online su LRCLib. Non tutti i brani hanno testi sincronizzati disponibili.",
        "Inizia", "Impostazioni", "Non ora", "Salvataggio non riuscito. Riprova.",
    ),
    "DE": (
        "DEINE MUSIK. EIN STÜCK NÄHER.", "Der Text folgt.\nDu genießt.",
        "Synchronisierte Liedtexte auf deinem Desktop, ohne Fensterwechsel.",
        "EINE VORSCHAU AUF DEINEM DESKTOP", "Demo • funktioniert auch ohne Musik",
        "Ein Stil für deinen Rhythmus", "Teste die Vorschau. Du kannst den Stil später ändern.",
        "Musik abspielen", "Öffne Spotify oder einen Player mit Windows-Medienunterstützung und spiele einen Titel ab.",
        "Dein eigener Stil", "Wähle einen Stil. Passe Farbe, Größe und Position in den Einstellungen an.",
        "Immer griffbereit", "Öffne neben der Uhr die ausgeblendeten Symbole (^) und klicke mit der rechten Maustaste auf STZLyrics.",
        "Liedtexte werden online von LRCLib geladen. Nicht für jeden Titel sind synchronisierte Texte verfügbar.",
        "Loslegen", "Einstellungen", "Später", "Speichern fehlgeschlagen. Bitte erneut versuchen.",
    ),
    "FR": (
        "VOTRE MUSIQUE. PLUS PROCHE.", "Les paroles suivent.\nVous profitez.",
        "Des paroles synchronisées sur votre bureau, sans changer de fenêtre.",
        "UN APERÇU SUR VOTRE BUREAU", "Démo • fonctionne même sans musique",
        "Un style pour votre rythme", "Essayez l'aperçu. Vous pourrez changer plus tard.",
        "Lancez la musique", "Ouvrez Spotify ou un lecteur compatible avec les médias Windows et lancez un morceau.",
        "À votre façon", "Choisissez un style. Réglez la couleur, la taille et la position dans les paramètres.",
        "Toujours à portée de main", "Près de l'horloge, ouvrez les icônes masquées (^) et faites un clic droit sur STZLyrics.",
        "Les paroles sont recherchées en ligne sur LRCLib. Certains morceaux n'ont pas de paroles synchronisées.",
        "Commencer", "Paramètres", "Plus tard", "Impossible d'enregistrer. Réessayez.",
    ),
    "JP": (
        "音楽を、もっと身近に。", "歌詞が流れる。\n音楽を楽しむ。",
        "ウィンドウを切り替えずに、デスクトップで同期歌詞を表示。",
        "デスクトップでのプレビュー", "デモ • 音楽を再生していなくても動作します",
        "あなたのリズムに合うスタイル", "プレビューで試せます。後から変更できます。",
        "音楽を再生", "Spotifyなど、Windowsのメディア機能に対応したプレーヤーで曲を再生してください。",
        "自分好みに", "スタイルを選び、設定で色・サイズ・位置を調整できます。",
        "いつでもアクセス", "時計の近くにある隠れたアイコン（^）を開き、STZLyricsを右クリックしてください。",
        "歌詞はLRCLibからオンラインで取得します。同期歌詞がない曲もあります。",
        "使い始める", "設定", "後で", "保存できませんでした。もう一度お試しください。",
    ),
}


def welcome_text(language: str, key: str) -> str:
    texts = dict(zip(_KEYS, _COPY.get(normalize_ui_language(language), _COPY["EN"])))
    return texts[key]


class DesktopPreview(QWidget):
    """Illustrative desktop with original demo text; no live media or network access."""

    def __init__(self, preset: str, language: str, parent=None) -> None:
        super().__init__(parent)
        self.preset = normalize_layout_preset(preset)
        self.language = language
        self._tick = 0
        self.setMinimumSize(280, 220)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setAccessibleName(welcome_text(language, "preview"))
        self.timer = QTimer(self)
        self.timer.setInterval(80)
        self.timer.timeout.connect(self._advance)

    def set_preset(self, preset: str) -> None:
        self.preset = normalize_layout_preset(preset)
        self.update()

    def _advance(self) -> None:
        self._tick += 1
        self.update()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.timer.start()

    def hideEvent(self, event) -> None:
        self.timer.stop()
        super().hideEvent(event)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(0, 0, w, h), 14, 14)
        p.setClipPath(clip)
        sky = QLinearGradient(0, 0, w, h)
        sky.setColorAt(0, QColor("#263d42"))
        sky.setColorAt(0.55, QColor("#17272e"))
        sky.setColorAt(1, QColor("#10181f"))
        p.fillRect(self.rect(), sky)
        # Abstract landscape, deliberately quiet behind the overlay text.
        for base, amplitude, color in ((0.49, 28, "#29444a"), (0.66, 20, "#20373b"), (0.83, 25, "#16282b")):
            path = QPainterPath()
            path.moveTo(0, h)
            for x in range(0, w + 9, 8):
                path.lineTo(x, h * base + math.sin(x / max(w, 1) * 5 + base * 8) * amplitude)
            path.lineTo(w, h)
            p.fillPath(path, QColor(color))

        def text(rect: QRectF, value: str, size: int, color: str, bold: bool = False) -> None:
            font = QFont("Segoe UI")
            font.setPixelSize(size)
            font.setBold(bold)
            p.setFont(font)
            p.setPen(QColor(color))
            value = p.fontMetrics().elidedText(value, Qt.ElideRight, int(rect.width()))
            p.drawText(rect, Qt.AlignCenter, value)

        model = build_layout_render_model(self.preset)
        portuguese = normalize_ui_language(self.language) == "PT-BR"
        lines = (
            ("O dia deixa a pressa passar", "A cidade muda de tom", "Cada passo encontra um ritmo", "A música vem nos levar", "Mais perto de onde quero estar")
            if portuguese else
            ("Let the busy day drift away", "The city finds another tone", "Every step becomes a rhythm", "The music carries us along", "A little closer to our home")
        )
        current = (self._tick // 36) % len(lines)
        center_y = (h - 65) / 2 - 12 if model.context_before else h * 0.58
        if model.show_header:
            text(QRectF(16, center_y - 38, w - 32, 22), "STZ Sessions  /  Demo", 12, "#b1c7ca")
        if model.context_before:
            for offset in (-2, -1, 1, 2):
                text(QRectF(16, center_y + offset * 27, w - 32, 25), lines[(current + offset) % len(lines)],
                     12, "#7f9a9d" if abs(offset) == 2 else "#b1c7ca")
        text(QRectF(16, center_y, w - 32, 27), lines[current], min(20, max(14, w // 25)), "#ffffff", True)

        p.fillRect(QRectF(0, h - 35, w, 35), QColor("#121a1f"))
        p.setPen(Qt.NoPen)
        for index, color in enumerate(("#98b3be", "#506e7b", "#df9c56", "#6e9b81")):
            p.setBrush(QColor(color))
            p.drawRoundedRect(QRectF(w / 2 - 47 + index * 26, h - 25, 15, 15), 4, 4)
        p.setPen(QPen(QColor("#8ea4ab"), 2))
        p.drawLine(w - 43, h - 17, w - 39, h - 21)
        p.drawLine(w - 39, h - 21, w - 35, h - 17)
        progress = (self._tick % 180) / 180
        p.fillRect(QRectF(18, h - 49, w - 36, 2), QColor("#375157"))
        p.fillRect(QRectF(18, h - 49, (w - 36) * progress, 2), QColor("#ffae57"))


class WelcomeWindow(QDialog):
    start_requested = Signal(str)
    settings_requested = Signal()

    def __init__(self, config: AppConfig, parent=None) -> None:
        super().__init__(parent)
        self.language = config.lyrics.language
        self.selected_preset = normalize_layout_preset(config.overlay.layout_preset)
        self.setWindowTitle("STZLyrics Overlay")
        self.setWindowIcon(load_app_icon())
        self.setModal(False)
        self.setMinimumSize(620, 480)
        self.resize(1000, 760)
        screen = self.screen()
        if screen is not None:
            available = screen.availableGeometry()
            self.resize(min(1000, available.width() - 40), min(760, available.height() - 60))
        self.setStyleSheet("""
            QDialog, QWidget#content { background: #121212; color: #f3f3f5; }
            QLabel { color: #f3f3f5; background: transparent; font-family: 'Segoe UI'; font-size: 13px; }
            QLabel#brand { font-size: 18px; font-weight: 700; }
            QLabel#eyebrow { color: #ffae57; font-size: 11px; font-weight: 700; }
            QLabel#heroTitle { font-size: 36px; font-weight: 700; }
            QLabel#muted { color: #a7a7b0; }
            QLabel#section { font-size: 19px; font-weight: 600; }
            QLabel#stepTitle { font-size: 14px; font-weight: 600; }
            QLabel#number { color: #ffae57; font-size: 12px; font-weight: 700; }
            QLabel#error { color: #ff9292; }
            QFrame#previewCard { background: #1e1e20; border: 1px solid #303034; border-radius: 16px; }
            QFrame#line { background: #303034; max-height: 1px; }
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical { background: #181818; width: 8px; }
            QScrollBar::handle:vertical { background: #49494f; border-radius: 4px; min-height: 24px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QPushButton { background: #222224; color: #dfdfe4; border: 1px solid #39393e;
                          border-radius: 9px; padding: 11px 16px; font-family: 'Segoe UI'; font-size: 13px; }
            QPushButton:hover { background: #2d2d30; border-color: #696970; }
            QPushButton:pressed { background: #353539; }
            QPushButton:checked { background: #352b21; border-color: #ffae57; color: #ffbe77; }
            QPushButton:focus { border: 2px solid #ffae57; }
            QPushButton#primary { background: #ffae57; border-color: #ffae57; color: #20150c; font-weight: 700; }
            QPushButton#primary:hover { background: #ffbf7b; }
            QPushButton#primary:pressed { background: #ed9740; }
            QPushButton#later { border-color: transparent; background: transparent; color: #a7a7b0; }
            QPushButton#later:hover { color: #ffffff; background: #222224; }
        """)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content = QWidget()
        content.setObjectName("content")
        body = QVBoxLayout(content)
        body.setContentsMargins(32, 24, 32, 24)
        body.setSpacing(20)
        brand = QHBoxLayout()
        icon = QLabel()
        icon.setPixmap(load_app_icon().pixmap(30, 30))
        brand.addWidget(icon)
        brand.addWidget(self._label("STZLyrics", "brand"))
        brand.addStretch()
        body.addLayout(brand)

        self.hero = QBoxLayout(QBoxLayout.LeftToRight)
        self.hero.setSpacing(28)
        intro = QVBoxLayout()
        intro.setSpacing(16)
        intro.addStretch()
        intro.addWidget(self._label(self._t("eyebrow"), "eyebrow"))
        intro.addWidget(self._label(self._t("title"), "heroTitle"))
        intro.addWidget(self._label(self._t("description"), "muted"))
        intro.addStretch()
        self.hero.addLayout(intro, 4)
        card = QFrame()
        card.setObjectName("previewCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(12)
        card_layout.addWidget(self._label(self._t("preview"), "eyebrow"))
        self.preview = DesktopPreview(self.selected_preset, self.language)
        card_layout.addWidget(self.preview, 1)
        note = self._label(self._t("preview_note"), "muted")
        card_layout.addWidget(note)
        self.hero.addWidget(card, 5)
        body.addLayout(self.hero)

        styles = QVBoxLayout()
        styles.setSpacing(8)
        styles.addWidget(self._label(self._t("choose"), "section"))
        styles.addWidget(self._label(self._t("choose_note"), "muted"))
        buttons = QHBoxLayout()
        self.preset_group = QButtonGroup(self)
        self.preset_buttons: dict[str, QPushButton] = {}
        for preset in ("minimal", "detailed", "context_2_2"):
            button = self._button(tr_settings_ui(self.language, f"preset_{preset}"))
            button.setCheckable(True)
            self.preset_group.addButton(button)
            button.setChecked(preset == self.selected_preset)
            button.clicked.connect(lambda checked=False, value=preset: self._select_preset(value))
            self.preset_buttons[preset] = button
            buttons.addWidget(button, 1)
        styles.addLayout(buttons)
        body.addLayout(styles)
        line = QFrame()
        line.setObjectName("line")
        line.setFixedHeight(1)
        body.addWidget(line)

        self.steps = QBoxLayout(QBoxLayout.LeftToRight)
        self.steps.setSpacing(24)
        for number, token in enumerate(("play", "style", "tray"), 1):
            step = QVBoxLayout()
            step.setSpacing(7)
            heading = QHBoxLayout()
            heading.addWidget(self._label(f"0{number}", "number"))
            heading.addWidget(self._label(self._t(f"{token}_title"), "stepTitle"), 1)
            step.addLayout(heading)
            step.addWidget(self._label(self._t(f"{token}_body"), "muted"))
            step.addStretch()
            self.steps.addLayout(step, 1)
        body.addLayout(self.steps)
        body.addWidget(self._label(self._t("availability"), "muted"))
        body.addStretch()
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        footer = QVBoxLayout()
        footer.setContentsMargins(32, 16, 32, 20)
        self.error_label = self._label("", "error")
        self.error_label.hide()
        footer.addWidget(self.error_label)
        actions = QHBoxLayout()
        actions.setSpacing(12)
        self.later_button = self._button(self._t("later"), "later")
        self.later_button.clicked.connect(self.reject)
        actions.addWidget(self.later_button)
        actions.addStretch()
        self.settings_button = self._button(self._t("settings"))
        self.settings_button.clicked.connect(self.settings_requested.emit)
        actions.addWidget(self.settings_button)
        self.start_button = self._button(self._t("begin"), "primary")
        self.start_button.setDefault(True)
        self.start_button.clicked.connect(lambda: self.start_requested.emit(self.selected_preset))
        actions.addWidget(self.start_button)
        footer.addLayout(actions)
        root.addLayout(footer)
        self._update_layout()

    def _t(self, key: str) -> str:
        return welcome_text(self.language, key)

    @staticmethod
    def _label(text: str, name: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName(name)
        label.setWordWrap(True)
        label.setTextFormat(Qt.PlainText)
        return label

    @staticmethod
    def _button(text: str, name: str = "") -> QPushButton:
        button = QPushButton(text)
        button.setObjectName(name)
        button.setCursor(Qt.PointingHandCursor)
        button.setAutoDefault(False)
        return button

    def _select_preset(self, preset: str) -> None:
        self.selected_preset = normalize_layout_preset(preset)
        self.preview.set_preset(self.selected_preset)

    def show_save_error(self) -> None:
        self.error_label.setText(self._t("error"))
        self.error_label.show()

    def _update_layout(self) -> None:
        direction = QBoxLayout.TopToBottom if self.width() < 840 else QBoxLayout.LeftToRight
        self.hero.setDirection(direction)
        self.steps.setDirection(direction)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "hero"):
            self._update_layout()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        _set_dark_windows_title_bar(int(self.winId()))
