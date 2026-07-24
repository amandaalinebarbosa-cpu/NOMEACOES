"""Scraper da página de profissionais cadastrados do SIGEO (CNPTJ).

Endpoint: https://aj.sigeo.jt.jus.br/aj2/internetaberto/profissionais.jsf
Colunas devolvidas: Nome | Categoria | Profissão | Especialidade

Estratégia:
  1. GET inicial para obter ViewState.
  2. Para cada tribunal (id JSF numérico), muda `form:unidade_input` via ajax,
     o que dispara o `valueChange` que renderiza a tabela.
  3. Pagina o DataTable até esgotar (rows=100 pra reduzir requisições).
"""
from __future__ import annotations

import os
import re
import time
from typing import Iterator

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential

from .scraper import TRIBUNAIS, USER_AGENT

load_dotenv()

URL = os.environ.get(
    "SIGEO_PERITOS_URL",
    "https://aj.sigeo.jt.jus.br/aj2/internetaberto/profissionais.jsf",
)
DELAY = float(os.environ.get("REQUEST_DELAY_SECONDS", "1.5"))


class SigeoPeritosClient:
    def __init__(self, url: str = URL, delay: float = DELAY):
        self.url = url
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9",
            "Referer": self.url,
        })
        self._vs: str | None = None

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=15))
    def _get(self):
        r = self.session.get(self.url, timeout=30); r.raise_for_status(); return r

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=15))
    def _post(self, data):
        h = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
             "Faces-Request": "partial/ajax",
             "X-Requested-With": "XMLHttpRequest"}
        r = self.session.post(self.url, data=data, headers=h, timeout=60)
        r.raise_for_status()
        return r

    def _extract_vs(self, text: str):
        m = re.search(r'name="javax\.faces\.ViewState"[^>]*value="([^"]+)"', text) \
            or re.search(r'ViewState[^"]*"[^>]*>\s*<!\[CDATA\[([^\]]+)\]\]>', text)
        if m:
            self._vs = m.group(1)

    def _parse_update(self, text: str) -> BeautifulSoup:
        m = re.search(
            r'<update id="form:resultadoPesquisa[^"]*">\s*<!\[CDATA\[(.*?)\]\]>\s*</update>',
            text, flags=re.DOTALL,
        )
        return BeautifulSoup(m.group(1) if m else text, "lxml")

    def carregar(self):
        r = self._get()
        self._extract_vs(r.text)

    def selecionar_tribunal(self, sigla: str) -> BeautifulSoup:
        if not self._vs:
            self.carregar()
        trib_id = TRIBUNAIS[sigla]
        data = [
            ("javax.faces.partial.ajax", "true"),
            ("javax.faces.source", "form:unidade"),
            ("javax.faces.partial.execute", "form:unidade"),
            ("javax.faces.partial.render",
             "form:resultadoPesquisa formBotoes form:uf form:municipio"),
            ("javax.faces.behavior.event", "valueChange"),
            ("javax.faces.partial.event", "change"),
            ("form", "form"),
            ("form:unidade_focus", ""),
            ("form:unidade_input", trib_id),
            ("form:uf_focus", ""),
            ("form:uf_input", ""),
            ("form:municipio_focus", ""),
            ("form:municipio_input", ""),
            ("javax.faces.ViewState", self._vs),
        ]
        time.sleep(self.delay)
        r = self._post(data)
        self._extract_vs(r.text)
        return self._parse_update(r.text)

    def paginar(self, first: int, rows: int = 100) -> BeautifulSoup:
        data = [
            ("javax.faces.partial.ajax", "true"),
            ("javax.faces.source", "form:resultadoPesquisa"),
            ("javax.faces.partial.execute", "form:resultadoPesquisa"),
            ("javax.faces.partial.render", "form:resultadoPesquisa"),
            ("form:resultadoPesquisa", "form:resultadoPesquisa"),
            ("form:resultadoPesquisa_pagination", "true"),
            ("form:resultadoPesquisa_first", str(first)),
            ("form:resultadoPesquisa_rows", str(rows)),
            ("form:resultadoPesquisa_encodeFeature", "true"),
            ("form", "form"),
            ("javax.faces.ViewState", self._vs),
        ]
        time.sleep(self.delay)
        r = self._post(data)
        self._extract_vs(r.text)
        return self._parse_update(r.text)

    @staticmethod
    def total_registros(soup: BeautifulSoup) -> int | None:
        el = soup.find(class_="ui-paginator-current")
        if not el:
            return None
        txt = el.get_text()
        # formatos: "(1 of 5)" ou "1-20 de 137"
        m = re.search(r"of\s+(\d+)", txt) or re.search(r"de\s+(\d+)", txt)
        return int(m.group(1)) if m else None

    @staticmethod
    def linhas(soup: BeautifulSoup) -> Iterator[dict]:
        tbody = soup.find(id="form:resultadoPesquisa_data") or soup.find("tbody")
        if not tbody:
            return
        for tr in tbody.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 4:
                continue
            cells = [td.get_text(" ", strip=True) for td in tds]
            yield {
                "nome":          cells[0],
                "categoria":     cells[1],
                "profissao":     cells[2],
                "especialidade": cells[3] or None,
            }
