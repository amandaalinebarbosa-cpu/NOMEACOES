"""Scraper da consulta pública de nomeações do SIGEO (JSF/PrimeFaces).

Endpoint: https://aj.sigeo.jt.jus.br/aj2/internetaberto/consultapublicanomeacoes.jsf

Filtros disponíveis na página pública:
  - Tribunal (SelectOneMenu com id interno numérico — ver TRIBUNAIS abaixo)
  - Período (data inicial / data final, dd/mm/aaaa)
  - UF, Município, Unidade (carregados por AJAX após escolher o tribunal)
  - Situação (checkbox: 3=CANCELADA, 5=ACEITA, 6=BAIXADA, 7=SERVIÇO PRESTADO)

Colunas do resultado:
  Número do processo | Tribunal | Unidade | Nome do profissional |
  Data | Valor | Situação

Filtros por nome/CPF/tipo de função NÃO existem no formulário público — são
aplicados como busca posterior no banco.
"""
from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass, field
from datetime import date
from typing import Iterator

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential

load_dotenv()

SIGEO_URL = os.environ.get(
    "SIGEO_URL",
    "https://aj.sigeo.jt.jus.br/aj2/internetaberto/consultapublicanomeacoes.jsf",
)
USER_AGENT = os.environ.get(
    "USER_AGENT",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0 Safari/537.36",
)
DELAY = float(os.environ.get("REQUEST_DELAY_SECONDS", "1.5"))

log = logging.getLogger(__name__)


# Sigla → value do <option> em form:unidadeAutenticadora_input
TRIBUNAIS: dict[str, str] = {
    "TRT1":  "2112", "TRT2":  "1638", "TRT3":  "2",    "TRT4":  "1452",
    "TRT5":  "1340", "TRT6":  "1261", "TRT7":  "1191", "TRT8":  "1011",
    "TRT9":  "908",  "TRT10": "873",  "TRT11": "832",  "TRT12": "764",
    "TRT13": "732",  "TRT14": "644",  "TRT15": "486",  "TRT16": "441",
    "TRT17": "405",  "TRT18": "350",  "TRT19": "324",  "TRT20": "102",
    "TRT21": "289",  "TRT22": "269",  "TRT23": "193",  "TRT24": "161",
}

# Situação → value
SITUACOES: dict[str, str] = {
    "CANCELADA": "3",
    "ACEITA": "5",
    "BAIXADA": "6",
    "SERVICO_PRESTADO": "7",
}


@dataclass
class Filtros:
    tribunal: str | None = None       # sigla, ex.: "TRT1"
    data_ini: date | None = None
    data_fim: date | None = None
    uf: str | None = None
    municipio: str | None = None
    unidade: str | None = None
    situacoes: list[str] = field(
        default_factory=lambda: list(SITUACOES.values())  # todas por padrão
    )


class SigeoClient:
    def __init__(self, url: str = SIGEO_URL, delay: float = DELAY):
        self.url = url
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9",
            "Referer": self.url,
        })
        self._view_state: str | None = None

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=15))
    def _get(self, url: str) -> requests.Response:
        r = self.session.get(url, timeout=30)
        r.raise_for_status()
        return r

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=15))
    def _post(self, url: str, data, ajax: bool = True) -> requests.Response:
        headers = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"}
        if ajax:
            headers["Faces-Request"] = "partial/ajax"
            headers["X-Requested-With"] = "XMLHttpRequest"
        r = self.session.post(url, data=data, headers=headers, timeout=60)
        r.raise_for_status()
        return r

    def _extract_view_state(self, text: str) -> None:
        # tanto do HTML quanto da resposta AJAX (<update id="...ViewState...">CDATA</update>)
        m = re.search(
            r'name="javax\.faces\.ViewState"[^>]*value="([^"]+)"', text
        ) or re.search(
            r'ViewState[^"]*"[^>]*>\s*<!\[CDATA\[([^\]]+)\]\]>', text
        )
        if m:
            self._view_state = m.group(1)

    def carregar(self) -> BeautifulSoup:
        r = self._get(self.url)
        self._extract_view_state(r.text)
        return BeautifulSoup(r.text, "lxml")

    def _vs(self) -> str:
        if not self._view_state:
            self.carregar()
        assert self._view_state, "Falha ao obter javax.faces.ViewState"
        return self._view_state

    def pesquisar(self, f: Filtros) -> BeautifulSoup:
        """Envia o formulário e devolve o HTML atualizado da página."""
        vs = self._vs()

        # lista de tuplas — situação aparece várias vezes com o mesmo name
        data: list[tuple[str, str]] = [
            ("javax.faces.partial.ajax", "true"),
            ("javax.faces.source", "form:comandoConsultar"),
            ("javax.faces.partial.execute", "@all"),
            ("javax.faces.partial.render", "form:resultadoPesquisa form:msgs"),
            ("form:comandoConsultar", "form:comandoConsultar"),
            ("form", "form"),
            ("form:unidadeAutenticadora_focus", ""),
            ("form:unidadeAutenticadora_input",
             TRIBUNAIS.get(f.tribunal or "", "") if f.tribunal else ""),
            ("form:dataInicial_input",
             f.data_ini.strftime("%d/%m/%Y") if f.data_ini else ""),
            ("form:dataFinal_input",
             f.data_fim.strftime("%d/%m/%Y") if f.data_fim else ""),
            ("form:uf_focus", ""),
            ("form:uf_input", f.uf or ""),
            ("form:municipio_focus", ""),
            ("form:municipio_input", f.municipio or ""),
            ("form:unidade_focus", ""),
            ("form:unidade_input", f.unidade or ""),
        ]
        for s in f.situacoes:
            data.append(("form:situacao", s))
        data.append(("javax.faces.ViewState", vs))

        time.sleep(self.delay)
        r = self._post(self.url, data, ajax=True)
        self._extract_view_state(r.text)

        # A resposta é XML de partial-update; extraímos o CDATA do
        # form:resultadoPesquisa e parseamos como HTML.
        m = re.search(
            r'<update id="form:resultadoPesquisa">\s*<!\[CDATA\[(.*?)\]\]>\s*</update>',
            r.text, flags=re.DOTALL,
        )
        html = m.group(1) if m else r.text
        return BeautifulSoup(html, "lxml")

    @staticmethod
    def linhas(soup: BeautifulSoup, tribunal_sigla: str | None = None) -> Iterator[dict]:
        """Extrai linhas da tabela form:resultadoPesquisa_data.

        Colunas (index): 0 processo | 1 tribunal | 2 unidade |
                         3 nome | 4 data | 5 valor | 6 situação
        """
        tbody = soup.find(id="form:resultadoPesquisa_data") or soup.find("tbody")
        if not tbody:
            return
        for tr in tbody.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 7:
                continue  # linha "Nenhum registro" tem colspan
            cells = [td.get_text(" ", strip=True) for td in tds]
            yield {
                "processo":  cells[0],
                "tribunal":  cells[1] or tribunal_sigla,
                "unidade":   cells[2],
                "nome":      cells[3],
                "data":      cells[4],
                "valor":     cells[5],
                "situacao":  cells[6],
            }


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
