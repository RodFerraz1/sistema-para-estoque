"""Captura uma tela da UI logado, com o Chrome headless pelo DevTools Protocol.

O cookie de sessão é `HttpOnly` e o Chrome headless não recebe cookie por linha de
comando. O script entra pelo `POST /login`, põe o cookie no Chrome, abre a URL, espera
as chamadas da página e grava o PNG. Sem `--email`, captura sem sessão (a tela de login).
A largura vai direto para o Chrome, então 390 px (celular) funciona sem iframe.

    uv run python -m scripts.capturar_tela http://localhost:8765/ui/ /tmp/painel.png \\
        --email carla@copilot.local --senha copilot-local
    uv run python -m scripts.capturar_tela http://localhost:8765/ui/aviso.html /tmp/aviso.png \\
        --email bia@copilot.local --senha copilot-local --largura 390 --altura 844 --celular
"""
from __future__ import annotations

import argparse
import base64
import itertools
import json
import shutil
import subprocess
import tempfile
import time
import urllib.request
from collections.abc import Sequence
from http.cookies import SimpleCookie
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from websockets.sync.client import ClientConnection, connect

from src.usuarios.dependencies import NOME_DO_COOKIE

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def token_de_sessao(url: str, email: str, senha: str) -> str:
    pedido = urllib.request.Request(
        urljoin(url, "/login"),
        data=json.dumps({"email": email, "senha": senha}).encode(),
        headers={"Content-Type": "application/json", "X-Requested-With": "fetch"},
        method="POST",
    )
    with urllib.request.urlopen(pedido) as resposta:
        cookie = SimpleCookie(resposta.headers["set-cookie"])
    return cookie[NOME_DO_COOKIE].value


class DevTools:
    def __init__(self, ws: ClientConnection) -> None:
        self._ws = ws
        self._ids = itertools.count(1)

    def chamar(self, metodo: str, **params: Any) -> dict[str, Any]:
        id_ = next(self._ids)
        self._ws.send(json.dumps({"id": id_, "method": metodo, "params": params}))
        while True:
            mensagem = json.loads(self._ws.recv())
            if mensagem.get("id") == id_:
                if "error" in mensagem:
                    raise RuntimeError(f"{metodo}: {mensagem['error']}")
                return mensagem.get("result", {})

    def esperar(self, evento: str, segundos: float) -> None:
        limite = time.monotonic() + segundos
        while time.monotonic() < limite:
            try:
                mensagem = json.loads(self._ws.recv(timeout=max(0.1, limite - time.monotonic())))
            except TimeoutError:
                return
            if mensagem.get("method") == evento:
                return


def _porta_do_devtools(perfil: Path) -> int:
    arquivo = perfil / "DevToolsActivePort"
    for _ in range(100):
        if arquivo.exists() and arquivo.read_text().strip():
            return int(arquivo.read_text().splitlines()[0])
        time.sleep(0.1)
    raise RuntimeError("o Chrome não abriu o DevTools")


def capturar(
    url: str,
    arquivo: Path,
    *,
    token: str | None,
    largura: int,
    altura: int,
    celular: bool,
    pagina_inteira: bool,
    espera: float,
    clicar: str | None = None,
    executar: Sequence[str] = (),
) -> None:
    perfil = Path(tempfile.mkdtemp(prefix="capturar-tela-"))
    chrome = subprocess.Popen(
        [CHROME, "--headless=new", "--remote-debugging-port=0", f"--user-data-dir={perfil}", "about:blank"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        porta = _porta_do_devtools(perfil)
        with urllib.request.urlopen(f"http://127.0.0.1:{porta}/json/list") as resposta:
            alvo = next(a for a in json.load(resposta) if a["type"] == "page")
        with connect(alvo["webSocketDebuggerUrl"], max_size=None) as ws:
            devtools = DevTools(ws)
            if token:
                devtools.chamar("Network.setCookie", name=NOME_DO_COOKIE, value=token, url=url, httpOnly=True)
            devtools.chamar(
                "Emulation.setDeviceMetricsOverride", width=largura, height=altura, deviceScaleFactor=1, mobile=celular
            )
            devtools.chamar("Page.enable")
            devtools.chamar("Page.navigate", url=url)
            devtools.esperar("Page.loadEventFired", 15)
            time.sleep(espera)
            if clicar:
                devtools.chamar("Runtime.evaluate", expression=f"document.querySelector({json.dumps(clicar)}).click()")
                time.sleep(1)
            for script in executar:
                devtools.chamar("Runtime.evaluate", expression=script)
                time.sleep(1.5)
            if pagina_inteira:
                conteudo = devtools.chamar("Page.getLayoutMetrics")["cssContentSize"]
                devtools.chamar(
                    "Emulation.setDeviceMetricsOverride",
                    width=largura,
                    height=int(conteudo["height"]),
                    deviceScaleFactor=1,
                    mobile=celular,
                )
            imagem = devtools.chamar("Page.captureScreenshot", format="png")["data"]
        arquivo.write_bytes(base64.b64decode(imagem))
    finally:
        chrome.terminate()
        chrome.wait(timeout=10)
        shutil.rmtree(perfil, ignore_errors=True)


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("url")
    parser.add_argument("arquivo", type=Path)
    parser.add_argument("--email")
    parser.add_argument("--senha")
    parser.add_argument("--largura", type=int, default=1280)
    parser.add_argument("--altura", type=int, default=1000)
    parser.add_argument("--celular", action="store_true", help="emula toque e viewport de celular")
    parser.add_argument("--pagina-inteira", action="store_true", help="captura a altura toda da página")
    parser.add_argument("--espera", type=float, default=4.0, help="segundos depois do load, para as chamadas da API")
    parser.add_argument("--clicar", help="seletor CSS clicado depois da espera, antes da captura (ex.: button.sino)")
    parser.add_argument(
        "--executar",
        action="append",
        default=[],
        help="JavaScript rodado na página depois do clique, um por vez com 1,5 s entre eles (repetível)",
    )
    args = parser.parse_args(argv)
    if args.email and not args.senha:
        parser.error("--email pede --senha")
    token = token_de_sessao(args.url, args.email, args.senha) if args.email else None
    capturar(
        args.url,
        args.arquivo,
        token=token,
        largura=args.largura,
        altura=args.altura,
        celular=args.celular,
        pagina_inteira=args.pagina_inteira,
        espera=args.espera,
        clicar=args.clicar,
        executar=args.executar,
    )
    print(args.arquivo)


if __name__ == "__main__":
    main()
