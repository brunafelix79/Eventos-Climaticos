"""Baixa o inventário oficial de estações pluviométricas da ANA e salva
apenas os códigos (e nome/coordenadas) em um CSV simples.

Camada: bronze (dado bruto do inventário oficial, sem tratamento).
"""

import csv
from pathlib import Path

import requests

INVENTARIOS = {
    "Pluviometrica": (
        "https://dadosabertos.ana.gov.br/api/download/v1/items/"
        "1a111215d36c424c9ff85ede46ada968/csv?layers=0"
    ),
    "Fluviometrica": (
        "https://dadosabertos.ana.gov.br/api/download/v1/items/"
        "d5f46121a21f4ce8972e31d6dbf4a65a/csv?layers=2"
    ),
}

# Raiz do projeto = dois níveis acima deste arquivo (src/ana/listar_estacoes.py)
RAIZ = Path(__file__).resolve().parents[2]
SAIDA_CSV = RAIZ / "data" / "bronze" / "ana" / "estacoes" / "codigos_estacoes.csv"


def main() -> None:
    SAIDA_CSV.parent.mkdir(parents=True, exist_ok=True)

    with open(SAIDA_CSV, "w", newline="", encoding="utf-8") as saida:
        escritor = csv.writer(saida)
        escritor.writerow(["codigo", "tipo", "nome", "latitude", "longitude"])
        total_geral = 0

        for tipo, url in INVENTARIOS.items():
            print(f"Baixando inventário oficial de estações {tipo.lower()} da ANA...")
            resposta = requests.get(url, timeout=120)
            resposta.raise_for_status()

            linhas = resposta.content.decode("utf-8-sig").splitlines()
            leitor = csv.DictReader(linhas)

            total_tipo = 0
            for linha in leitor:
                codigo = linha.get("CD")
                if not codigo:
                    continue
                escritor.writerow(
                    [codigo, tipo, linha.get("NM"), linha.get("Y"), linha.get("X")]
                )
                total_tipo += 1

            print(f"  {total_tipo} estação(ões) {tipo.lower()}(s) encontrada(s).")
            total_geral += total_tipo

    print(f"\nTotal: {total_geral} estação(ões) salva(s) em {SAIDA_CSV}")


if __name__ == "__main__":
    main()
