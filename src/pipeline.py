"""
Orquestrador do pipeline de extração de dados.

Roda, em sequência, todos os scripts de coleta que já existem em src/
(ana, inmet, noaa...), sem depender de Databricks, Airflow ou banco SQL —
só chama cada script como um processo separado (do mesmo jeito que você
rodaria manualmente, um por um), registra o resultado de cada etapa e
segue pra próxima mesmo se uma delas falhar.

Uso (rodar sempre a partir da raiz do projeto):

    Rodar o pipeline inteiro:
        python src/pipeline.py

    Rodar só algumas etapas:
        python src/pipeline.py --etapas ana_chuva,inmet

    Pular uma etapa (ex.: NOAA, que baixa ~280 MB e demora):
        python src/pipeline.py --pular noaa

    Passar argumentos extras pra uma etapa específica (ex.: limitar
    estações num teste rápido):
        python src/pipeline.py --etapas ana_chuva -- --limit 5

Cada execução gera um log em logs/pipeline_AAAAMMDD_HHMMSS.txt com o
resultado (ok/erro) e a duração de cada etapa.
"""

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]  # raiz do projeto (src/pipeline.py -> ..)

# Ordem de execução. args_padrao = argumentos passados ao script sempre que
# ele for chamado sem --etapas nem argumentos extras específicos.
ETAPAS = [
    {
        "nome": "ana_estacoes",
        "script": RAIZ / "src" / "ana" / "listar_estacoes.py",
        "args_padrao": [],
    },
    {
        "nome": "ana_chuva",
        "script": RAIZ / "src" / "ana" / "buscar_chuva_todas.py",
        "args_padrao": ["--limit", "0"],
    },
    {
        "nome": "ana_cota",
        "script": RAIZ / "src" / "ana" / "buscar_cota_todas.py",
        "args_padrao": ["--limit", "0"],
    },
    {
        "nome": "inmet",
        "script": RAIZ / "src" / "inmet" / "baixar_alertas_inmet.py",
        "args_padrao": [],
    },
    {
        "nome": "noaa",
        "script": RAIZ / "src" / "noaa" / "baixar_el_nino.py",
        "args_padrao": [],
    },
]

PASTA_LOGS = RAIZ / "logs"


def parse_args():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--etapas", type=str, default=None,
        help=f"Lista separada por vírgula das etapas a rodar, na ordem desejada "
             f"(padrão: todas, na ordem: {', '.join(e['nome'] for e in ETAPAS)}).",
    )
    parser.add_argument(
        "--pular", type=str, default=None,
        help="Lista separada por vírgula das etapas a NÃO rodar (ignorado se --etapas for usado).",
    )
    parser.add_argument(
        "extra", nargs=argparse.REMAINDER,
        help="Argumentos extras repassados para cada script chamado (coloque depois de --). "
             "Só faz sentido combinado com --etapas apontando pra uma única etapa.",
    )
    return parser.parse_args()


def selecionar_etapas(args) -> list:
    etapas_por_nome = {e["nome"]: e for e in ETAPAS}

    if args.etapas:
        nomes = [n.strip() for n in args.etapas.split(",") if n.strip()]
        invalidos = [n for n in nomes if n not in etapas_por_nome]
        if invalidos:
            nomes_validos = ", ".join(etapas_por_nome)
            print(f"Etapa(s) desconhecida(s): {', '.join(invalidos)}. Válidas: {nomes_validos}")
            sys.exit(1)
        return [etapas_por_nome[n] for n in nomes]

    if args.pular:
        pular = {n.strip() for n in args.pular.split(",") if n.strip()}
        invalidos = pular - etapas_por_nome.keys()
        if invalidos:
            nomes_validos = ", ".join(etapas_por_nome)
            print(f"Etapa(s) desconhecida(s) em --pular: {', '.join(invalidos)}. Válidas: {nomes_validos}")
            sys.exit(1)
        return [e for e in ETAPAS if e["nome"] not in pular]

    return list(ETAPAS)


def main() -> None:
    args = parse_args()
    etapas = selecionar_etapas(args)
    argumentos_extras = args.extra[1:] if args.extra and args.extra[0] == "--" else args.extra

    if argumentos_extras and len(etapas) > 1:
        print(
            "Aviso: argumentos extras foram passados mas mais de uma etapa será "
            "executada; eles serão repassados a TODAS as etapas selecionadas."
        )

    PASTA_LOGS.mkdir(parents=True, exist_ok=True)
    inicio_execucao = datetime.now()
    arquivo_log = PASTA_LOGS / f"pipeline_{inicio_execucao.strftime('%Y%m%d_%H%M%S')}.txt"

    resultados = []

    print(f"Pipeline iniciado em {inicio_execucao.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Etapas: {', '.join(e['nome'] for e in etapas)}\n")

    with open(arquivo_log, "w", encoding="utf-8") as log:
        log.write(f"Pipeline iniciado em {inicio_execucao.strftime('%Y-%m-%d %H:%M:%S')}\n")
        log.write(f"Etapas: {', '.join(e['nome'] for e in etapas)}\n\n")

        for etapa in etapas:
            nome = etapa["nome"]
            script = etapa["script"]
            argumentos = argumentos_extras if argumentos_extras else etapa["args_padrao"]

            if not script.exists():
                print(f"[{nome}] PULADO: script não encontrado em {script}")
                log.write(f"[{nome}] PULADO: script não encontrado em {script}\n")
                resultados.append((nome, "PULADO", 0.0))
                continue

            comando = [sys.executable, str(script), *argumentos]
            print(f"[{nome}] Rodando: {' '.join(comando)}")
            log.write(f"[{nome}] Rodando: {' '.join(comando)}\n")

            inicio_etapa = datetime.now()
            resultado = subprocess.run(comando, cwd=RAIZ)
            duracao = (datetime.now() - inicio_etapa).total_seconds()

            if resultado.returncode == 0:
                status = "OK"
                print(f"[{nome}] OK ({duracao:.1f}s)\n")
            else:
                status = f"ERRO (código {resultado.returncode})"
                print(f"[{nome}] ERRO (código {resultado.returncode}, {duracao:.1f}s) — seguindo para a próxima etapa.\n")

            log.write(f"[{nome}] {status} — {duracao:.1f}s\n\n")
            resultados.append((nome, status, duracao))

    duracao_total = (datetime.now() - inicio_execucao).total_seconds()

    print("=" * 50)
    print("Resumo do pipeline:")
    for nome, status, duracao in resultados:
        print(f"  {nome:<15} {status:<20} {duracao:.1f}s")
    print(f"\nTempo total: {duracao_total:.1f}s")
    print(f"Log salvo em: {arquivo_log}")

    houve_erro = any(status.startswith("ERRO") for _, status, _ in resultados)
    sys.exit(1 if houve_erro else 0)


if __name__ == "__main__":
    main()
