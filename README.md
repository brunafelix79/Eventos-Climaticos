# hidroaccess

![Alt](docs/images/ecotec.png "Identidade visual do grupo de pesquisa Ecotecnologias")

## Sumário
- [Sobre](#sobre)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Instalação](#instalação)
- [Biblioteca `hidroaccess`](#biblioteca-hidroaccess)
  - [Access](#classe-access)
  - [safe_request_token](#método-safe_request_token)
  - [request_telemetrica](#método-request_telemetrica)
  - [request_sedimentos](#método-request_sedimentos)
  - [request_cota](#método-request_cota)
  - [request_chuva](#método-request_chuva)
  - [atualizar_credenciais](#método-atualizar_credenciais)
- [Scripts de coleta (`src/`)](#scripts-de-coleta-src)
- [Dados (`data/`)](#dados-data)
- [Desenvolvimento e testes](#desenvolvimento-e-testes)
- [Contato](#contato)

## Sobre
Projeto para automatizar a coleta de dados hidrológicos e climáticos usados
pelo grupo de pesquisa Ecotecnologias: chuva e cota de estações da ANA,
alertas meteorológicos do INMET e o índice El Niño/La Niña (NOAA). Inclui a
biblioteca `hidroaccess`, cliente Python para a API HidroWebService da ANA.
Não possui nenhuma afiliação ou relação com a ANA, o INMET ou a NOAA.

## Estrutura do projeto
O projeto é organizado em camadas por pasta (estilo "medalhão": bronze →
silver → gold), sem depender de Databricks, Spark ou um banco SQL — só
pastas e scripts Python comuns, pensado pra rodar local no Visual Studio.

```
Hidro/
├── hidroaccess/         # biblioteca: cliente da API da ANA (não mexe em arquivo)
├── src/                 # scripts de coleta, um subpacote por fonte de dado
│   ├── ana/              # chuva, cota e inventário de estações (ANA)
│   ├── inmet/             # alertas meteorológicos (INMET)
│   ├── noaa/               # índice El Niño / La Niña (NOAA)
│   └── previsao/            # previsão numérica/satélite (ainda não implementado)
├── data/                 # camadas de dado, por pasta
│   ├── bronze/            # dado bruto, como a fonte entrega (gerado pelos scripts em src/)
│   ├── silver/             # dado limpo/unificado (a construir)
│   └── gold/                # dado pronto pra análise/dashboard (a construir)
├── tests/                # testes automatizados da biblioteca hidroaccess
└── docs/                 # imagens e documentação extra
```

- **bronze**: exatamente o que os scripts de `src/` baixam da fonte oficial
  (ANA, INMET, NOAA), sem nenhum tratamento — só append incremental e
  deduplicação básica.
- **silver**: onde entraria a limpeza/junção desses dados brutos (ex.: cruzar
  chuva + cota + alertas por data e estação). Ainda não existe nenhum script
  aqui; é o próximo passo natural do projeto.
- **gold**: dado já agregado/pronto pra consumo final (relatório, dashboard,
  modelo). Também ainda não existe.

Os dados dentro de `data/` **não são versionados no git** (veja
`.gitignore`) — são grandes, mudam a cada execução e são 100%
reproduzíveis rodando os scripts de novo. Só as pastas (via `.gitkeep`) ficam
no repositório, pra estrutura existir mesmo em um clone novo.

> ⚠️ O arquivo `.env` original desse projeto tinha credenciais reais salvas.
> Ele foi removido do pacote reorganizado (só ficou o `.env.example`, sem
> segredo nenhum). Antes de subir pro GitHub, troque a senha usada nesse
> `.env` — se ele já foi commitado em algum histórico de git antes, o ideal
> é considerá-la exposta e trocar de qualquer forma.

## Instalação
```bash
pip install -e .
# ou, para desenvolvimento (inclui pytest):
pip install -e ".[dev]"
```

Depois, copie `.env.example` para `.env` na raiz do projeto e preencha suas
credenciais da ANA:
```bash
cp .env.example .env
```

## Biblioteca `hidroaccess`

### Classe *Access*
A classe `Access` funciona como uma "sessão": é por ela que as comunicações
com a API são realizadas. Os parâmetros de inicialização são o ID e a Senha
adquiridos previamente junto à ANA.

```python
from hidroaccess import Access

sessao = Access("SEU_ID", "SUA_SENHA")
```

### Método *safe_request_token()*
Retorna um token (`str`) para validação de outras requisições, tentando
novamente algumas vezes em caso de falha transitória. Se as credenciais
forem inválidas, retorna `'-1'`.

```python
token = sessao.safe_request_token()
```

### Método *request_telemetrica()*
Requisita dados de uma estação telemétrica. Retorna uma lista de
dicionários; cada um tem a chave `'Hora_Medicao'` com a data/horário da
medição correspondente.

- `estacao_codigo` (int): código de oito dígitos da estação.
- `data_inicio` / `data_fim` (str): formato `'YYYY-MM-DD'`.
- `token` (str): token válido obtido em `safe_request_token()`.
- `tipo` (`'Adotada'` ou `'Detalhada'`): opcional; `'Adotada'` é o padrão.
  `'Detalhada'` retorna variáveis adicionais.

```python
retorno = sessao.request_telemetrica(85900000, "2020-01-01", "2020-01-05", token, tipo="Detalhada")
```

### Método *request_sedimentos()*
Dados de sedimentos de uma estação convencional.

```python
retorno = sessao.request_sedimentos(72980000, "2020-01-01", "2020-01-05", token)
```

### Método *request_cota()*
Dados de cota de uma estação convencional.

```python
retorno = sessao.request_cota(72980000, "2020-01-01", "2020-01-05", token)
```

### Método *request_chuva()*
Dados de chuva de uma estação convencional.

```python
retorno = sessao.request_chuva(47000, "2020-01-01", "2020-01-05", token)
```

### Método *atualizar_credenciais()*
Sobrescreve as credenciais salvas na sessão.

```python
sessao.atualizar_credenciais("NOVO_ID", "NOVA_SENHA")
```

Estrutura interna da biblioteca:
```
hidroaccess/
  __init__.py     # exporta Access e as exceções públicas
  constants.py    # URLs dos endpoints e limites da API
  exceptions.py   # HidroAccessError e subclasses
  client.py       # classe Access + funções puras de janelas/parâmetros
  decoders.py     # decodificação das respostas em listas de dicionários
```

## Scripts de coleta (`src/`)
Cada script grava sempre no mesmo lugar dentro de `data/bronze/`,
independente de onde você o executa (o caminho é resolvido a partir da
posição do próprio arquivo, não do diretório atual):

| Script | O que faz | Onde salva |
|---|---|---|
| `src/ana/listar_estacoes.py` | Baixa o inventário oficial de estações (pluviométricas + fluviométricas) | `data/bronze/ana/estacoes/codigos_estacoes.csv` |
| `src/ana/buscar_chuva.py` | Exemplo simples: busca chuva de algumas estações e só imprime no terminal | — (não grava arquivo) |
| `src/ana/buscar_chuva_todas.py` | Busca chuva de todas as estações, com checkpoint incremental | `data/bronze/ana/chuva/` |
| `src/ana/buscar_cota_todas.py` | Busca cota de todas as estações, com checkpoint incremental | `data/bronze/ana/cota/` |
| `src/inmet/baixar_alertas_inmet.py` | Baixa avisos meteorológicos ativos/recentes do INMET | `data/bronze/inmet/alertas/alertas_inmet.csv` |
| `src/noaa/baixar_el_nino.py` | Baixa o dataset NOAA ERSSTv5 e extrai a série Niño 3.4 | `data/bronze/noaa/el_nino/` |
| `src/previsao/*.py` | Ainda não implementados (eram scripts vazios no projeto original) | `data/bronze/previsao/` (a criar) |

Exemplo de uso (rodando da raiz do projeto):
```bash
python src/ana/listar_estacoes.py
python src/ana/buscar_chuva_todas.py --limit 0
python src/inmet/baixar_alertas_inmet.py
python src/noaa/baixar_el_nino.py
```

## Dados (`data/`)
```
data/
  bronze/
    ana/
      estacoes/   -> codigos_estacoes.csv
      chuva/      -> chuva_todas_estacoes.csv, estado_estacoes.json (checkpoint)
      cota/       -> cota_todas_estacoes.csv, estado_estacoes_cota.json (checkpoint)
    inmet/
      alertas/    -> alertas_inmet.csv
    noaa/
      el_nino/    -> sst.mnmean.nc (bruto, ~280 MB), sst_nino34.csv
  silver/         -> (vazio; próximo passo: dado limpo/unificado)
  gold/           -> (vazio; próximo passo: dado pronto pra análise)
```

Veja [CHANGELOG.md](CHANGELOG.md) para o detalhamento do que mudou em
relação à versão anterior.

## Desenvolvimento e testes
```bash
pip install -e ".[dev]"
pytest -v
```
Os testes não fazem chamadas reais à API nem exigem credenciais — usam
mocks e dados simulados.

## Contato
Para mais informações sobre o projeto, sugestões ou reportar erros:
- Miguel Brondani - Desenvolvedor: brondani.miguel@gmail.com
- Daniel Allasia - Professor Orientador: dallasia@gmail.com
- Ecotecnologias - Grupo de Pesquisa: eco@ecotecnologias.org
- https://github.com/mBrond/hidroaccess
