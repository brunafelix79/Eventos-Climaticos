"""Cliente de acesso à API HidroWebService da ANA."""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Iterable, Iterator, Tuple

import aiohttp
import requests

from . import decoders
from .constants import (
    CONVENCIONAL_ENDPOINTS,
    MAX_DIAS_CONVENCIONAL,
    TELEMETRICA_ENDPOINTS,
    TOKEN_ENDPOINT,
    TOKEN_INVALIDO,
)
from .exceptions import DataInvalidaError, TipoDadoInvalidoError, TokenInvalidoError


class Access:
    """Sessão de acesso à API HidroWebService da ANA.

    Guarda as credenciais do usuário e oferece métodos para requisitar séries
    de dados de estações telemétricas e convencionais (chuva, cota, sedimento).

    Example:
        >>> sessao = Access("SEU_ID", "SUA_SENHA")
        >>> token = sessao.safe_request_token()
        >>> dados = sessao.request_telemetrica(85900000, "2020-01-01", "2020-01-05", token)
    """

    def __init__(self, id: str, senha: str) -> None:
        self._id = id
        self._senha = senha

    def atualizar_credenciais(self, id: str, senha: str) -> None:
        """Substitui as credenciais salvas na sessão."""
        self._id = id
        self._senha = senha

    # --- autenticação --------------------------------------------------

    def requisitar_token(self) -> requests.Response:
        """Faz uma única tentativa de obter um token com as credenciais atuais."""
        headers = {"Identificador": self._id, "Senha": self._senha}
        return requests.get(TOKEN_ENDPOINT, headers=headers)

    def safe_request_token(self, tentativas_maximas: int = 5) -> str:
        """Requisita um token válido, tentando novamente em caso de falha transitória.

        Args:
            tentativas_maximas: número máximo de tentativas antes de desistir.

        Returns:
            O token de autenticação, ou '-1' se as credenciais forem inválidas
            (HTTP 401) ou o número máximo de tentativas for atingido.
        """
        resposta = self.requisitar_token()
        if resposta.status_code == 401:
            return TOKEN_INVALIDO

        tentativas = 1
        while resposta.status_code != 200 and tentativas < tentativas_maximas:
            resposta = self.requisitar_token()
            tentativas += 1

        if resposta.status_code != 200:
            return TOKEN_INVALIDO

        return json.loads(resposta.content)["items"]["tokenautenticacao"]

    @staticmethod
    def _cabecalho_autenticacao(token: str) -> dict:
        if token == TOKEN_INVALIDO:
            raise TokenInvalidoError(f"Token inválido: {token}.")
        return {"Authorization": f"Bearer {token}"}

    # --- estações telemétricas ------------------------------------------

    def request_telemetrica(
        self,
        estacao_codigo: int,
        data_inicio: str,
        data_fim: str,
        token: str,
        tipo: str = "Adotada",
        max_requisicoes_simultaneas: int = 20,
    ) -> list:
        """Requisita a série de dados de uma estação telemétrica.

        Args:
            estacao_codigo: código de oito dígitos da estação.
            data_inicio: data inicial no formato 'YYYY-MM-DD'.
            data_fim: data final no formato 'YYYY-MM-DD'.
            token: token válido obtido em safe_request_token().
            tipo: 'Adotada' (padrão, menos variáveis) ou 'Detalhada'.
            max_requisicoes_simultaneas: tamanho máximo dos lotes assíncronos.

        Returns:
            Lista de dicionários, cada um com a chave 'Hora_Medicao' e as
            variáveis medidas correspondentes.
        """
        if tipo not in TELEMETRICA_ENDPOINTS:
            raise TipoDadoInvalidoError(
                f"Parâmetro 'tipo' inválido: {tipo!r}. Deve ser 'Adotada' ou 'Detalhada'."
            )
        return asyncio.run(
            self._request_telemetrica_async(
                estacao_codigo, data_inicio, data_fim, token, tipo, max_requisicoes_simultaneas
            )
        )

    async def _request_telemetrica_async(
        self, estacao_codigo, data_inicio, data_fim, token, tipo, tamanho_lote
    ) -> list:
        inicio = _validar_data(data_inicio)
        fim = _validar_data(data_fim)
        cabecalho = self._cabecalho_autenticacao(token)
        url = TELEMETRICA_ENDPOINTS[tipo]

        parametros = [
            _parametros_telemetrica(estacao_codigo, dia_final_bloco, intervalo)
            for dia_final_bloco, intervalo in _janelas_telemetrica(inicio, fim)
        ]

        respostas = await _baixar_em_lotes(url, parametros, cabecalho, tamanho_lote)
        return decoders.decode_respostas(respostas, tipo)

    # --- estações convencionais ------------------------------------------

    def request_sedimentos(
        self, estacao_codigo: int, data_inicio: str, data_fim: str, token: str,
        max_requisicoes_simultaneas: int = 20,
    ) -> list:
        """Requisita dados de sedimentos de uma estação convencional."""
        return asyncio.run(
            self._request_convencional_async(
                estacao_codigo, data_inicio, data_fim, token, "Sedimento", max_requisicoes_simultaneas
            )
        )

    def request_cota(
        self, estacao_codigo: int, data_inicio: str, data_fim: str, token: str,
        max_requisicoes_simultaneas: int = 20,
    ) -> list:
        """Requisita dados de cota de uma estação convencional."""
        return asyncio.run(
            self._request_convencional_async(
                estacao_codigo, data_inicio, data_fim, token, "Cota", max_requisicoes_simultaneas
            )
        )

    def request_chuva(
        self, estacao_codigo: int, data_inicio: str, data_fim: str, token: str,
        max_requisicoes_simultaneas: int = 20,
    ) -> list:
        """Requisita dados de chuva de uma estação convencional."""
        return asyncio.run(
            self._request_convencional_async(
                estacao_codigo, data_inicio, data_fim, token, "Chuva", max_requisicoes_simultaneas
            )
        )

    async def _request_convencional_async(
        self, estacao_codigo, data_inicio, data_fim, token, tipo, tamanho_lote
    ) -> list:
        inicio = _validar_data(data_inicio)
        fim = _validar_data(data_fim)
        cabecalho = self._cabecalho_autenticacao(token)
        url = CONVENCIONAL_ENDPOINTS[tipo]

        parametros = [
            _parametros_convencional(estacao_codigo, janela_inicio, janela_fim)
            for janela_inicio, janela_fim in _janelas_convencional(inicio, fim)
        ]

        respostas = await _baixar_em_lotes(url, parametros, cabecalho, tamanho_lote)
        return decoders.decode_respostas(respostas, tipo)


# --- funções auxiliares puras (sem I/O, fáceis de testar) -----------------


def _validar_data(data: str) -> datetime:
    """Converte uma string 'YYYY-MM-DD' em datetime, ou levanta DataInvalidaError."""
    try:
        return datetime.strptime(data, "%Y-%m-%d")
    except (ValueError, TypeError):
        raise DataInvalidaError(f"Parâmetro 'data' inválido: {data!r}. Deve ser 'YYYY-MM-DD'.")


def _tamanho_bloco_telemetrica(dias_restantes: int) -> int:
    """Escolhe o maior bloco (30/21/14/7/2/1 dias) que cabe nos dias restantes."""
    for limite in (30, 21, 14, 7, 2):
        if dias_restantes >= limite:
            return limite
    return 1


def _intervalo_busca(qtd_dias: int) -> str:
    """Converte um tamanho de bloco no parâmetro 'Range Intervalo de busca' da API."""
    for dias, intervalo in ((30, "DIAS_30"), (21, "DIAS_21"), (14, "DIAS_14"),
                             (7, "DIAS_7"), (2, "DIAS_2"), (0, "HORA_24")):
        if qtd_dias >= dias:
            return intervalo


def _janelas_telemetrica(inicio: datetime, fim: datetime) -> Iterator[Tuple[datetime, str]]:
    """Gera (data_final_do_bloco, intervalo_de_busca) cobrindo [inicio, fim).

    A API telemétrica não aceita um intervalo [início, fim] diretamente: cada
    requisição pede "N dias terminando em uma data". Esta função particiona o
    período total nesses blocos, usando sempre o maior bloco possível.
    """
    atual = inicio
    while atual != fim:
        qtd_dias = _tamanho_bloco_telemetrica((fim - atual).days)
        atual += timedelta(days=qtd_dias)
        yield atual - timedelta(days=1), _intervalo_busca(qtd_dias)


def _parametros_telemetrica(estacao_codigo: int, dia_final_bloco: datetime, intervalo: str) -> dict:
    return {
        "Código da Estação": estacao_codigo,
        "Tipo Filtro Data": "DATA_LEITURA",
        "Data de Busca (yyyy-MM-dd)": dia_final_bloco.strftime("%Y-%m-%d"),
        "Range Intervalo de busca": intervalo,
    }


def _janelas_convencional(
    inicio: datetime, fim: datetime, max_dias: int = MAX_DIAS_CONVENCIONAL
) -> Iterator[Tuple[datetime, datetime]]:
    """Gera (início, fim) de cada bloco de até `max_dias` dias cobrindo [inicio, fim]."""
    atual = inicio
    while atual < fim:
        fim_bloco = min(atual + timedelta(days=max_dias), fim)
        yield atual, fim_bloco
        atual = fim_bloco + timedelta(days=1)


def _parametros_convencional(estacao_codigo: int, inicio: datetime, fim: datetime) -> dict:
    return {
        "Código da Estação": estacao_codigo,
        "Tipo Filtro Data": "DATA_LEITURA",
        "Data Inicial (yyyy-MM-dd)": inicio.strftime("%Y-%m-%d"),
        "Data Final (yyyy-MM-dd)": fim.strftime("%Y-%m-%d"),
    }


async def _baixar_uma(session: aiohttp.ClientSession, url: str, params: dict) -> bytes:
    async with session.get(url, params=params) as resposta:
        return await resposta.content.read()


async def _baixar_em_lotes(
    url: str, lista_parametros: Iterable[dict], cabecalho: dict, tamanho_lote: int
) -> list:
    """Baixa todas as respostas, agrupando as requisições em lotes assíncronos de `tamanho_lote`."""
    lista_parametros = list(lista_parametros)
    respostas = []
    for inicio_lote in range(0, len(lista_parametros), tamanho_lote):
        lote = lista_parametros[inicio_lote: inicio_lote + tamanho_lote]
        async with aiohttp.ClientSession(headers=cabecalho) as session:
            respostas.extend(
                await asyncio.gather(*(_baixar_uma(session, url, params) for params in lote))
            )
    return respostas
