# Changelog

## 1.0.0
Primeira versão.

- Biblioteca `hidroaccess`: cliente Python para a API HidroWebService da ANA
  (`Access`, `safe_request_token`, `request_telemetrica`, `request_sedimentos`,
  `request_cota`, `request_chuva`, `atualizar_credenciais`).
- Scripts de coleta em `src/`: inventário de estações e chuva/cota (ANA),
  alertas meteorológicos (INMET), índice El Niño/La Niña (NOAA).
- Orquestrador `src/pipeline.py`, que roda todas as coletas em sequência.
- Primeiro tratamento silver (`src/silver/tratar_chuva.ipynb`) e gold
  (`src/gold/gerar_parquet_chuva.ipynb`) pra chuva.
