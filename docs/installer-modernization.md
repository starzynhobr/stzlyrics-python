# Instalador moderno: proposta inicial

## Estado atual

O aplicativo é Python/PySide6. `build-windows.ps1` gera `dist/STZLyricsOverlay/` com PyInstaller e usa Inno Setup 7 para gerar um Setup por usuário, com atalhos e desinstalador. O `AppId` do Inno deve permanecer estável para atualizações. A próxima versão de ambos os pacotes é `1.2.0`.

## Opção recomendada para o primeiro protótipo

Personalizar o assistente do próprio Inno Setup. O projeto já tem toda a lógica de instalação, atualização, atalhos e remoção nele. Um protótipo visual permite avaliar se uma capa de marca, páginas com menos passos e textos claros entregam a experiência desejada com um único Setup e sem outro runtime.

## Se a direção visual exigir Tauri

É tecnicamente viável usar Tauri como interface e Inno em modo silencioso como mecanismo de instalação:

1. Gerar o aplicativo Python com PyInstaller e, depois, o Setup Inno.
2. Compilar o frontend Tauri como **bootstrapper**, sem usar o instalador NSIS/MSI padrão do Tauri para instalar o próprio bootstrapper.
3. Para distribuir um único EXE, incorporar o Setup Inno versionado ao binário Rust do bootstrapper, extrair em diretório temporário e verificar sua integridade antes de executar.
4. Executar o Inno com argumentos fixos como `/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP- /LOG`, aguardar o processo e traduzir seu código de saída em sucesso, falha ou reinício necessário.
5. Deixar o Inno como único responsável por arquivos instalados, registro, atalhos, atualização e desinstalação. Após sucesso, o bootstrapper pode oferecer a abertura do aplicativo; a entrada `[Run]` atual já usa `skipifsilent`.

Tauri usa WebView2 no Windows. O runtime é distribuído com o Windows 11; no Windows 10, a presença dele precisa ser considerada no bootstrapper. A distribuição precisa testar instalação nova, atualização sobre a mesma `AppId`, cancelamento, falha, reinício, atalhos e desinstalação. O protótipo deve ser assinado antes de distribuição pública.

Não empacotar o bootstrapper Tauri com seu instalador NSIS/MSI padrão e então chamar o Inno: isso criaria dois ciclos de instalação. Um executável Tauri sem bundle e com o payload incorporado é a forma coerente de explorar essa arquitetura.

## Referências

- [Tauri: distribuição e `--no-bundle`](https://v2.tauri.app/distribute/)
- [Tauri: instaladores Windows e WebView2](https://v2.tauri.app/distribute/windows-installer/)
- [Inno Setup: parâmetros de linha de comando](https://jrsoftware.org/ishelp/topic_setupcmdline.htm)
- [Inno Setup: códigos de saída](https://jrsoftware.org/ishelp/topic_setupexitcodes.htm)
