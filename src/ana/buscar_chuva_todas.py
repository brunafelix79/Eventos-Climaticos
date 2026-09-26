"""
Busca dados de chuva de VÁRIAS estações pluviométricas da ANA, com suporte a
atualização incremental.

Passo 1: baixa (ou lê de um arquivo local) a lista de códigos de estação.
Passo 2: para cada código, verifica em data/bronze/ana/chuva/estado_estacoes.json
         até que data já foi buscado, e busca só o período novo (ou o
         histórico completo, na primeira vez).
Passo 3: acrescenta os dados novos em
         data/bronze/ana/chuva/chuva_todas_estacoes.csv (não apaga o que já
         existia) e atualiza o checkpoint de cada estação.

Camada: bronze (dado bruto da API, só com incremental append; nenhum
tratamento/limpeza é feito aqui — isso é trabalho da camada silver).

A lista de estações vem do inventário público e oficial da ANA
(Portal de Dados Abertos, não exige login):
https://dadosabertos.ana.gov.br/datasets/1a111215d36c424c9ff85ede46ada968_0

Uso:
    Carga inicial (todas as estações, histórico completo):
        python src/ana/buscar_chuva_todas.py --limit 0

    Atualização incremental (rodar de novo depois, quantas vezes quiser):
        python src/ana/buscar_chuva_todas.py --limit 0

    O script decide sozinho, por estação, se é a primeira vez (usa
    --data-inicio-padrao) ou uma atualização (usa o checkpoint salvo).
"""

import argparse
import csv
import json
import os
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

from hidroaccess import Access, HidroAccessError

# Raiz do projeto = dois níveis acima deste arquivo (src/ana/buscar_chuva_todas.py)
RAIZ = Path(__file__).resolve().parents[2]

load_dotenv(dotenv_path=RAIZ / ".env")

ID = (os.getenv("HIDRO_ID") or "").strip()
SENHA = (os.getenv("HIDRO_SENHA") or "").strip()

INVENTARIO_URL = (
    "https://dadosabertos.ana.gov.br/api/download/v1/items/"
    "1a111215d36c424c9ff85ede46ada968/csv?layers=0"
)

PASTA_BRONZE_CHUVA = RAIZ / "data" / "bronze" / "ana" / "chuva"
SAIDA_CSV = PASTA_BRONZE_CHUVA / "chuva_todas_estacoes.csv"
ESTADO_JSON = PASTA_BRONZE_CHUVA / "estado_estacoes.json"


def obter_codigos_estacao(limite: int, arquivo_local: str | None) -> list:
    """Retorna uma lista de códigos de estação (strings)."""
    if arquivo_local:
        with open(arquivo_local, encoding="utf-8") as f:
            codigos = [linha.strip() for linha in f if linha.strip()]
        print(f"{len(codigos)} código(s) lido(s) de {arquivo_local!r}.")
        return codigos[:limite] if limite else codigos

    print("Baixando inventário oficial de estações pluviométricas da ANA...")
    resposta = requests.get(INVENTARIO_URL, timeout=120)
    resposta.raise_for_status()

    linhas = resposta.content.decode("utf-8-sig").splitlines()
    leitor = csv.DictReader(linhas)
    codigos = [linha["CD"] for linha in leitor if linha.get("CD")]

    print(f"{len(codigos)} estação(ões) encontrada(s) no inventário.")
    return codigos[:limite] if limite else codigos


def carregar_estado() -> dict:
    """Lê o checkpoint (última data já buscada) de cada estação."""
    if not ESTADO_JSON.exists():
        return {}
    with open(ESTADO_JSON, encoding="utf-8") as f:
        return json.load(f)


def salvar_estado(estado: dict) -> None:
    with open(ESTADO_JSON, "w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--limit", type=int, default=20,
        help="Número máximo de estações a processar (padrão: 20). Use 0 para todas.",
    )
    parser.add_argument(
        "--estacoes", type=str, default=None,
        help="Caminho para um .txt com um código de estação por linha, "
             "em vez de baixar o inventário completo da ANA.",
    )
    parser.add_argument(
        "--delay", type=float, default=1.0,
        help="Segundos de espera entre uma estação e outra (padrão: 1.0).",
    )
    parser.add_argument(
        "--data-inicio-padrao", type=str, default="2020-01-01",
        help="Data de início (yyyy-MM-dd) usada na PRIMEIRA busca de cada "
             "estação, quando ainda não há checkpoint salvo (padrão: 2020-01-01).",
    )
    args = parser.parse_args()

    if not ID or not SENHA:
        print("Erro: defina HIDRO_ID e HIDRO_SENHA no arquivo .env")
        sys.exit(1)

    PASTA_BRONZE_CHUVA.mkdir(parents=True, exist_ok=True)

    sessao = Access(ID, SENHA)

    print("Solicitando token de autenticação...")
    token = sessao.safe_request_token()
    if token == "-1":
        print("Erro: credenciais inválidas (usuário ou senha incorretos).")
        sys.exit(1)
    print("Token obtido com sucesso.\n")
    ultimo_token = time.monotonic()

    codigos = obter_codigos_estacao(args.limit, args.estacoes)
    if not codigos:
        print("Nenhum código de estação encontrado. Encerrando.")
        sys.exit(1)

    estado = carregar_estado()
    hoje = date.today().strftime("%Y-%m-%d")

    csv_existe = SAIDA_CSV.exists()
    arquivo_saida = open(SAIDA_CSV, "a", newline="", encoding="utf-8")
    escritor = None
    escreveu_cabecalho = csv_existe and SAIDA_CSV.stat().st_size > 0

    total = len(codigos)
    estacoes_ok = 0
    estacoes_com_erro = 0
    estacoes_em_dia = 0

    try:
        for indice, codigo in enumerate(codigos, start=1):
            if time.monotonic() - ultimo_token > 55 * 60:
                print("Renovando token (validade de 60 min)...")
                token = sessao.safe_request_token()
                ultimo_token = time.monotonic()
                if token == "-1":
                    print("Erro: token inválido ao renovar. Encerrando.")
                    break

            try:
                estacao_codigo_int = int(codigo)
            except ValueError:
                print(f"[{indice}/{total}] Estação {codigo}: código inválido, pulando.")
                estacoes_com_erro += 1
                continue

            ultima_data_salva = estado.get(codigo)
            if ultima_data_salva:
                data_inicio = (
                    datetime.strptime(ultima_data_salva, "%Y-%m-%d") + timedelta(days=1)
                ).strftime("%Y-%m-%d")
            else:
                data_inicio = args.data_inicio_padrao

            if data_inicio > hoje:
                estacoes_em_dia += 1
                continue

            print(f"[{indice}/{total}] Estação {codigo} ({data_inicio} a {hoje})...", end=" ")

            dados = None
            max_tentativas = 3
            for tentativa in range(1, max_tentativas + 1):
                try:
                    dados = sessao.request_chuva(estacao_codigo_int, data_inicio, hoje, token)
                    break
                except HidroAccessError as erro:
                    print(f"erro ({erro}).")
                    estacoes_com_erro += 1
                    dados = None
                    break
                except Exception as erro:
                    if tentativa < max_tentativas:
                        espera = args.delay * (2 ** tentativa)
                        print(
                            f"falhou (tentativa {tentativa}/{max_tentativas}: "
                            f"{type(erro).__name__}: {erro}), tentando de novo em {espera:.0f}s...",
                            end=" ",
                        )
                        time.sleep(espera)
                    else:
                        print(f"desistindo após {max_tentativas} tentativas ({type(erro).__name__}: {erro}).")
                        estacoes_com_erro += 1
                        dados = None

            if dados is None:
                time.sleep(args.delay)
                continue

            if dados:
                if not escreveu_cabecalho:
                    campos = list(dados[0].keys())
                    escritor = csv.DictWriter(arquivo_saida, fieldnames=campos)
                    escritor.writeheader()
                    escreveu_cabecalho = True
                elif escritor is None:
                    campos = list(dados[0].keys())
                    escritor = csv.DictWriter(arquivo_saida, fieldnames=campos)

                for registro in dados:
                    registro.setdefault("codigoestacao", codigo)
                    escritor.writerow(registro)

                arquivo_saida.flush()
                print(f"{len(dados)} registro(s) novo(s) salvo(s).")
            else:
                print("sem dados novos no período.")

            # Marca a estação como atualizada até hoje, mesmo sem dados novos,
            # para não ficar reprocessando o mesmo período vazio toda vez.
            estado[codigo] = hoje
            salvar_estado(estado)
            estacoes_ok += 1
            time.sleep(args.delay)
    except KeyboardInterrupt:
        print("\nInterrompido pelo usuário (Ctrl+C). Progresso salvo até aqui.")
    finally:
        arquivo_saida.close()
        salvar_estado(estado)

    print(
        f"\nConcluído: {estacoes_ok} estação(ões) processada(s), "
        f"{estacoes_em_dia} já em dia, {estacoes_com_erro} com erro, "
        f"de {total} no total."
    )
    print(f"Resultado salvo em: {SAIDA_CSV}")
    print(f"Checkpoint salvo em: {ESTADO_JSON}")


if __name__ == "__main__":
    main()
