# STZLyrics Overlay (Python MVP)

Overlay de letras sincronizadas para Windows 10/11, inspirado no fluxo da skin Rainmeter existente (`STZLyrics.ini`, `Lyrics.lua`, `Settings.ini`), mas reimplementado em Python.

## MVP entregue

- Janela overlay sem borda, transparente, always-on-top
- Texto com antialiasing + sombra configurável
- Drag para mover
- Click-through opcional (`WS_EX_TRANSPARENT`)
- Snap opcional na borda/taskbar
- Persistência de posição por monitor + escala (DPI)
- Polling GSMTC (priorizando Spotify quando possível)
- Busca LRCLib com timeout + retry/backoff
- Parser LRC + sincronização incremental com offset
- Cache local LRU com índice JSON persistido
- Ícone na tray para toggles e recarregar letra

## Estrutura

```text
app/
  main.py
  controller.py
  config.py
  logging_utils.py
  config.default.json
  services/
    media_session.py
    lrclib_client.py
    lyrics_sync.py
    cache.py
  ui/
    overlay_window.py
    system_tray.py
    windows_api.py
tests/
  test_lrc_parser.py
```

## Requisitos

- Windows 10/11
- Python 3.10+
- Player compatível com Windows Media Session (Spotify geralmente funciona)

## Instalação

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -U pip
pip install -e .
```

## Executar

```powershell
python -m app.main
```

Ou, após `pip install -e .`:

```powershell
stzlyrics-overlay
```

## Configuração

O app cria a configuração em:

- `%APPDATA%\STZLyricsOverlay\config.json`

Pastas geradas:

- `%APPDATA%\STZLyricsOverlay\cache\` (arquivos `.lrc`/`.txt` + `index.json`)
- `%APPDATA%\STZLyricsOverlay\logs\`

Arquivo padrão de referência no repositório:

- `app/config.default.json`

Parâmetros principais:

- `font.family`, `font.size`, `font.color`, `font.shadow.*`
- `lyrics.offset_seconds`
- `lyrics.update_interval_ms`
- `cache.max_entries`
- `overlay.click_through`
- `overlay.snap_to_taskbar`
- `overlay.positions` (salvo automaticamente por monitor/DPI)

## Tray (atalho rápido)

- Mostrar/Ocultar overlay
- Toggle click-through
- Toggle snap
- Recarregar letra
- Abrir pasta de config
- Sair

## Testes (parser/sync)

```powershell
pytest
```

## Observações / limitações do MVP

- Sem tela gráfica de configurações (usa arquivo JSON + tray)
- Fallback para letra não sincronizada mostra mensagem (`Sem letra sincronizada`)
- A seleção de sessão GSMTC prioriza Spotify e sessões em `Playing`, mas pode variar conforme o player
- O overlay restaura posição com base no monitor principal ao iniciar (salva por monitor/DPI quando movido)

