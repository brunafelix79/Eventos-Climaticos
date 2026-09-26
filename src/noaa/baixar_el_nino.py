"""
Baixa o dataset ERSSTv5 (Extended Reconstructed Sea Surface Temperature) da
NOAA — temperatura da superfície do mar em grade global, mensal, desde 1854
— e extrai a série temporal média da região Niño 3.4 (5°N–5°S, 170°W–120°W),
a mais usada para acompanhar El Niño / La Niña.

Camada: bronze (o .nc bruto da NOAA) -> um recorte simples de região/tempo
já é feito aqui porque é isso que a fonte entrega de útil (o grid global
completo não seria versionado); qualquer limpeza/junção adicional com outras
séries fica para a camada silver.

Fonte oficial (não exige login):
https://downloads.psl.noaa.gov/Datasets/noaa.ersst.v5/sst.mnmean.nc

Uso:
    python src/noaa/baixar_el_nino.py

Gera dois arquivos em data/bronze/noaa/el_nino/:
    sst.mnmean.nc    -> arquivo bruto da NOAA (grade global completa, ~280 MB;
                        não é versionado no git, veja .gitignore)
    sst_nino34.csv   -> série mensal recortada da região Niño 3.4 (poucos KB)
"""

import sys
from pathlib import Path

import numpy as np
import requests

NETCDF_URL = "https://downloads.psl.noaa.gov/Datasets/noaa.ersst.v5/sst.mnmean.nc"

# Raiz do projeto = dois níveis acima deste arquivo (src/noaa/baixar_el_nino.py)
RAIZ = Path(__file__).resolve().parents[2]
PASTA_BRONZE_NOAA = RAIZ / "data" / "bronze" / "noaa" / "el_nino"
ARQUIVO_NC = PASTA_BRONZE_NOAA / "sst.mnmean.nc"
ARQUIVO_CSV = PASTA_BRONZE_NOAA / "sst_nino34.csv"

# Caixa geográfica da região Niño 3.4 (convenção de longitude 0-360 do dataset)
LAT_MIN, LAT_MAX = -5, 5
LON_MIN, LON_MAX = 190, 240  # equivalente a 170°W-120°W


def baixar_netcdf() -> None:
    if ARQUIVO_NC.exists():
        print(f"{ARQUIVO_NC} já existe, pulando download.")
        return

    print("Baixando dataset ERSSTv5 da NOAA (~280 MB, pode demorar alguns minutos)...")
    with requests.get(NETCDF_URL, stream=True, timeout=300) as resposta:
        resposta.raise_for_status()
        total = int(resposta.headers.get("content-length", 0))
        baixado = 0
        with open(ARQUIVO_NC, "wb") as f:
            for pedaco in resposta.iter_content(chunk_size=1024 * 1024):
                f.write(pedaco)
                baixado += len(pedaco)
                if total:
                    pct = baixado / total * 100
                    print(f"\r  {baixado / 1e6:.0f} MB / {total / 1e6:.0f} MB ({pct:.0f}%)", end="")
        print()
    print("Download concluído.")


def extrair_nino34() -> None:
    try:
        from netCDF4 import Dataset, num2date
    except ImportError:
        print("Erro: falta o pacote netCDF4. Instale com: pip install netCDF4")
        sys.exit(1)

    print("Lendo o NetCDF e recortando a região Niño 3.4...")
    with Dataset(ARQUIVO_NC) as ds:
        lat = ds.variables["lat"][:]
        lon = ds.variables["lon"][:]
        tempo = ds.variables["time"]
        sst = ds.variables["sst"][:]  # shape: (tempo, lat, lon)

        datas = num2date(tempo[:], tempo.units, only_use_cftime_datetimes=False)

        mascara_lat = (lat >= LAT_MIN) & (lat <= LAT_MAX)
        mascara_lon = (lon >= LON_MIN) & (lon <= LON_MAX)

        recorte = sst[:, mascara_lat, :][:, :, mascara_lon]
        media_mensal = np.nanmean(recorte, axis=(1, 2))

    with open(ARQUIVO_CSV, "w", encoding="utf-8") as f:
        f.write("data,sst_nino34_c\n")
        for data, valor in zip(datas, media_mensal):
            if np.ma.is_masked(valor):
                continue
            f.write(f"{data.strftime('%Y-%m-%d')},{valor:.3f}\n")

    print(f"{len(media_mensal)} mês(es) salvos em {ARQUIVO_CSV}")


def main() -> None:
    PASTA_BRONZE_NOAA.mkdir(parents=True, exist_ok=True)
    baixar_netcdf()
    extrair_nino34()


if __name__ == "__main__":
    main()
