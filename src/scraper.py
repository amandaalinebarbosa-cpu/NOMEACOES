"""Scraper da consulta pública de nomeações do SIGEO (JSF/PrimeFaces).

A página é uma aplicação JSF, então cada requisição precisa:
  1. Baixar a página inicial para obter cookies (JSESSIONID) e o javax.faces.ViewState.
  2. Postar o formulário replicando o ajax do PrimeFaces (cabeçalho Faces-Request: partial/ajax).

Os nomes exatos dos campos (ids do formulário JSF, ex.:
`formConsulta:dataInicial_input`) variam por versão do sistema. Inspecione o
DevTools do navegador na página real e ajuste FIELD_MAP abaixo.
"""
from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass, field
from datetime import date
from typing import Iterable, Iterator

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential

load_dotenv()

SIGEO_URL = os.environ.get(
    "SIGEO_URL",
    "https://aj.sigeo.jt.jus.br/aj2/internetaberto/consultapublicanomeacoes.jsf",
)
USER_AGENT = os.environ.get("USER_AGENT", "Mozilla/5.0 NomeacoesBot/0.1")
DELAY = float(os.environ.get("REQUEST_DELAY_SECONDS", "1.5"))

log = logging.getLogger(__name__)


# Ajuste após inspecionar o formulário JSF real (View Source / DevTools).
FIELD_MAP = {
    "form":          "formConsulta",
    "tribunal":      "formConsulta:tribunal",
    "data_ini":      "formConsulta:dataInicial_input",
    "data_fim":      "formConsulta:dataFinal_input",
    "nome":          "formConsulta:nomeNomeado",
    "cpf":           "formConsulta:cpfNomeado",
    "tipo_funcao":   "formConsulta:tipoFuncao",
    "botao_pesquisar": "formConsulta:btnPesquisar",
    "tabela_resultado": "formConsulta:tabelaResultado",
}


@dataclass
class Filtros:
    tribunal: str | None = None       # ex.: "TRT1"
    data_ini: date | None = None
    data_fim: date | None = None
    nome: str | None = None
    cpf: str | None = None
    tipo_funcao: str | None = None
    extras: dict[str, str] = field(default_factory=dict)


class SigeoClient:
    def __init__(self, url: str = SIGEO_URL, delay: float = DELAY):
        self.url = url
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9",
        })
        self._view_state: str | None = None

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=15))
    def _get(self, url: str) -> requests.Response:
        resp = self.session.get(url, timeout=30)
        resp.raise_for_status()
        return resp

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=15))
    def _post(self, url: str, data: dict, ajax: bool = True) -> requests.Response:
        headers = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"}
        if ajax:
            headers["Faces-Request"] = "partial/ajax"
            headers["X-Requested-With"] = "XMLHttpRequest"
        resp = self.session.post(url, data=data, headers=headers, timeout=60)
        resp.raise_for_status()
        return resp

    def carregar(self) -> BeautifulSoup:
        r = self._get(self.url)
        soup = BeautifulSoup(r.text, "lxml")
        vs = soup.find("input", {"name": "javax.faces.ViewState"})
        if vs:
            self._view_state = vs.get("value")
        return soup

    def _view_state_or_load(self) -> str:
        if not self._view_state:
            self.carregar()
        assert self._view_state, "Falha ao obter javax.faces.ViewState"
        return self._view_state

    def pesquisar(self, f: Filtros) -> BeautifulSoup:
        vs = self._view_state_or_load()
        form = FIELD_MAP["form"]
        payload = {
            "javax.faces.partial.ajax": "true",
            "javax.faces.source": FIELD_MAP["botao_pesquisar"],
            "javax.faces.partial.execute": "@all",
            "javax.faces.partial.render": FIELD_MAP["tabela_resultado"],
            FIELD_MAP["botao_pesquisar"]: FIELD_MAP["botao_pesquisar"],
            form: form,
            "javax.faces.ViewState": vs,
        }
        if f.tribunal:    payload[FIELD_MAP["tribunal"]] = f.tribunal
        if f.data_ini:    payload[FIELD_MAP["data_ini"]] = f.data_ini.strftime("%d/%m/%Y")
        if f.data_fim:    payload[FIELD_MAP["data_fim"]] = f.data_fim.strftime("%d/%m/%Y")
        if f.nome:        payload[FIELD_MAP["nome"]] = f.nome
        if f.cpf:         payload[FIELD_MAP["cpf"]] = f.cpf
        if f.tipo_funcao: payload[FIELD_MAP["tipo_funcao"]] = f.tipo_funcao
        payload.update(f.extras)

        time.sleep(self.delay)
        r = self._post(self.url, payload, ajax=True)
        soup = BeautifulSoup(r.text, "lxml")
        # PrimeFaces devolve <update id="javax.faces.ViewState:0">novo_vs</update>
        m = re.search(r'id="javax\.faces\.ViewState[^"]*"[^>]*>\s*<!\[CDATA\[([^\]]+)', r.text)
        if m:
            self._view_state = m.group(1)
        return soup

    @staticmethod
    def linhas(soup: BeautifulSoup) -> Iterator[dict]:
        """Extrai linhas da tabela de resultados.

        Ajuste conforme os cabeçalhos reais devolvidos pelo SIGEO.
        Cabeçalhos esperados (exemplo): Processo | Tribunal | Órgão Julgador |
        Nome | CPF | Função | Especialidade | Data | Situação | Valor | Magistrado
        """
        table = soup.find("table")
        if not table:
            return
        headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
        for tr in table.select("tbody tr"):
            cells = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
            if not cells:
                continue
            row = dict(zip(headers, cells))
            yield row


def parse_valor(txt: str | None) -> float | None:
    if not txt:
        return None
    t = txt.replace("R$", "").replace(".", "").replace(",", ".").strip()
    try:
        return float(t)
    except ValueError:
        return None


def parse_data(txt: str | None) -> date | None:
    if not txt:
        return None
    try:
        d, m, y = txt.strip().split("/")
        return date(int(y), int(m), int(d))
    except Exception:
        return None
