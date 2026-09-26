# Changelog — reescrita v2.0.0

Reescrita completa do zero, mantendo a mesma lógica e a mesma API pública
(`Access`, `safe_request_token`, `request_telemetrica`, `request_sedimentos`,
`request_cota`, `request_chuva`, `atualizar_credenciais`). O que mudou foi
**como** o código está organizado, não **o que** ele faz.

## Estrutura
- `access.py` (1 arquivo, 1 classe com tudo dentro) virou 4 módulos:
  - `constants.py` — URLs e limites da API.
  - `exceptions.py` — erros próprios (`TokenInvalidoError`, `DataInvalidaError`,
    `TipoDadoInvalidoError`) em vez de `ValueError` genérico.
  - `client.py` — a classe `Access` (rede) + funções puras de cálculo de
    janelas/parâmetros, testáveis sem chamar a API.
  - `decoders.py` — decodificação das respostas.

## Removido
- Métodos e parâmetros já marcados como obsoletos/mortos no código original:
  `_criaParams`, e os parâmetros `horarioInicial`/`horarioFinal` de
  `_main_request_convencionais`, que nunca eram passados pelos métodos públicos.

## `decoders.py`
- As listas de 60+ chaves repetidas (`Chuva_01..31`, `Cota_01..31`) agora são
  geradas por uma função (`_campos_numerados`) em vez de escritas à mão.
- `_decode_request_adotada` e `_decode_request_detalhada` viraram uma única
  função genérica (`_decodificar_serie_temporal`) parametrizada pela lista de
  campos. O mesmo para chuva/cota/sedimento (`_decodificar_registro_diario`).

## `client.py`
- A lógica de "quantos dias buscar em cada bloco" e "monte os parâmetros da
  requisição" foi extraída da corrotina de rede para funções puras
  (`_janelas_telemetrica`, `_janelas_convencional`, `_parametros_*`), que não
  fazem I/O e podem ser testadas diretamente, sem mocks de rede nem
  credenciais.
- O agrupamento em lotes assíncronos (`_baixar_em_lotes`) ficou separado da
  geração dos parâmetros — antes as duas coisas estavam misturadas no mesmo
  laço `while`.
- Pequena correção: o lote assíncrono original tinha um "off-by-one"
  (`len(blocoAsync) <= qtdDownloadsAsync`, ou seja, lotes de 21 em vez de 20).
  Isso não muda os dados retornados, só o tamanho dos lotes de requisições
  simultâneas.

## Testes
- Os testes originais dependiam de um arquivo `tests/credenciais.txt` com
  credenciais reais e faziam chamadas de verdade à API da ANA.
- Os novos testes usam `unittest.mock` para simular respostas HTTP e testam
  as funções puras isoladamente — rodam offline, sem credenciais, em
  milissegundos.

## Não mudou
- Os nomes e a assinatura dos métodos públicos.
- O formato dos parâmetros enviados à API (mesmas chaves, mesmos valores).
- O formato dos dicionários retornados (mesmas chaves em `Adotada`,
  `Detalhada`, `Chuva`, `Cota`, `Sedimento`).
- A regra de negócio de particionamento de datas (blocos de 30/21/14/7/2/1
  dias para telemétricas; blocos de até 366 dias para convencionais).
