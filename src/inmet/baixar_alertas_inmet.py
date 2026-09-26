"""
Baixa os avisos meteorológicos ativos/recentes do INMET (Alert-AS): chuva
intensa, tempestade, vendaval, geada, baixa umidade, etc.

Camada: bronze (avisos brutos do feed RSS oficial, só com deduplicação por
link/id; nenhum tratamento adicional é feito aqui).

Fonte oficial (pública, não exige login):
https://apiprevmet3.inmet.gov.br/avisos/rss

Cada execução ACRESCENTA os avisos novos ao final do CSV (nunca sobrescreve).
Avisos já salvos em execuções anteriores (mesmo link/id) não são duplicados.

Uso:
    python src/inmet/baixar_alertas_inmet.py

Gera/atualiza: data/bronze/inmet/alertas/alertas_inmet.csv
"""

import csv
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

RSS_URL = "https://apiprevmet3.inmet.gov.br/avisos/rss"

# Raiz do projeto = dois níveis acima deste arquivo (src/inmet/baixar_alertas_inmet.py)
RAIZ = Path(__file__).resolve().parents[2]
SAIDA_CSV = RAIZ / "data" / "bronze" / "inmet" / "alertas" / "alertas_inmet.csv"

CAMPOS = [
    "evento", "severidade",
    "data_inicio", "hora_inicio",
    "data_fim", "hora_fim",
    "descricao", "areas", "link",
]


def extrair_campo(tabela_html: str, rotulo: str) -> str:
    """Extrai o valor de uma linha <tr><th>rotulo</th><td>valor</td></tr>."""
    padrao = rf"<th[^>]*>{re.escape(rotulo)}</th>\s*<td[^>]*>(.*?)</td>"
    m = re.search(padrao, tabela_html, re.DOTALL)
    if not m:
        return ""
    valor = m.group(1)
    valor = re.sub(r"<[^>]+>", " ", valor)
    valor = re.sub(r"\s+", " ", valor).strip()
    return valor


def separar_data_hora(timestamp: str) -> tuple:
    """'2026-09-08 10:00:00.0' -> ('2026-09-08', '10:00:00')."""
    if not timestamp:
        return "", ""
    partes = timestamp.split(" ")
    data = partes[0] if len(partes) > 0 else ""
    hora = partes[1].split(".")[0] if len(partes) > 1 else ""
    return data, hora


def carregar_links_ja_salvos() -> set:
    if not SAIDA_CSV.exists():
        return set()
    with open(SAIDA_CSV, encoding="utf-8") as f:
        leitor = csv.DictReader(f)
        return {linha["link"] for linha in leitor if linha.get("link")}


def main() -> None:
    SAIDA_CSV.parent.mkdir(parents=True, exist_ok=True)

    print("Baixando avisos do INMET (Alert-AS)...")
    resposta = requests.get(RSS_URL, timeout=60)
    resposta.raise_for_status()

    raiz_xml = ET.fromstring(resposta.content)
    itens = raiz_xml.findall(".//item")
    print(f"{len(itens)} aviso(s) no feed.")

    links_ja_salvos = carregar_links_ja_salvos()

    csv_existe = SAIDA_CSV.exists() and SAIDA_CSV.stat().st_size > 0
    novos = 0

    with open(SAIDA_CSV, "a", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=CAMPOS)
        if not csv_existe:
            escritor.writeheader()

        for item in itens:
            link = item.findtext("link", default="")
            if not link or link in links_ja_salvos:
                continue

            descricao_html = item.findtext("description", default="")

            evento = extrair_campo(descricao_html, "Evento")
            severidade = extrair_campo(descricao_html, "Severidade")
            inicio_raw = extrair_campo(descricao_html, "Início")
            fim_raw = extrair_campo(descricao_html, "Fim")
            descricao = extrair_campo(descricao_html, "Descrição")
            areas = extrair_campo(descricao_html, "Área")

            data_inicio, hora_inicio = separar_data_hora(inicio_raw)
            data_fim, hora_fim = separar_data_hora(fim_raw)

            escritor.writerow({
                "evento": evento,
                "severidade": severidade,
                "data_inicio": data_inicio,
                "hora_inicio": hora_inicio,
                "data_fim": data_fim,
                "hora_fim": hora_fim,
                "descricao": descricao,
                "areas": areas,
                "link": link,
            })
            links_ja_salvos.add(link)
            novos += 1

    print(f"{novos} aviso(s) novo(s) acrescentado(s) em {SAIDA_CSV}")
    print("(avisos já existentes no arquivo não foram duplicados)")


if __name__ == "__main__":
    main()
