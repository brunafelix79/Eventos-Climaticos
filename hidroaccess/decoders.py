"""Decodificação das respostas brutas da API em listas de dicionários.

A API retorna JSON codificado em latin-1. Cada tipo de estação/série tem um
conjunto de campos diferente; em vez de repetir listas gigantes de chaves
(como no formato original), os campos numerados (Chuva_01..31, Cota_01..31)
são gerados programaticamente e o restante é declarado uma única vez.
"""

import json

from .exceptions import TipoDadoInvalidoError


def _campos_numerados(prefixo: str, quantidade: int = 31) -> tuple:
    """Gera pares '<prefixo>_NN' / '<prefixo>_NN_Status' para NN de 01 a `quantidade`."""
    campos = []
    for numero in range(1, quantidade + 1):
        sufixo = f"{numero:02d}"
        campos.append(f"{prefixo}_{sufixo}")
        campos.append(f"{prefixo}_{sufixo}_Status")
    return tuple(campos)


CAMPOS_ADOTADA = ("Chuva_Adotada", "Cota_Adotada", "Vazao_Adotada")
CAMPOS_DETALHADA = ("Chuva_Acumulada", "Chuva_Adotada", "Cota_Adotada", "Cota_Sensor", "Vazao_Adotada")

CAMPOS_CHUVA = _campos_numerados("Chuva") + (
    "Data_Hora_Dado", "Data_Ultima_Alteracao", "Dia_Maxima", "Maxima", "Maxima_Status",
    "Nivel_Consistencia", "Numero_Dias_de_Chuva", "Numero_Dias_de_Chuva_Status",
    "Tipo_Medicao_Chuvas", "Total", "Total_Anual", "Total_Anual_Status",
    "Total_Status", "codigoestacao",
)

CAMPOS_COTA = _campos_numerados("Cota") + (
    "Data_Hora_Dado", "Data_Ultima_Alteracao", "Dia_Maxima", "Dia_Minima", "Maxima",
    "Maxima_Status", "Media", "Media_Anual", "Media_Anual_Status", "Media_Status",
    "Mediadiaria", "Minima", "Minima_Status", "Tipo_Medicao_Cotas", "codigoestacao",
    "nivelconsistencia",
)

CAMPOS_SEDIMENTO = (
    "Area_Molhada", "Concentracao_PPM", "Concentracao_da_Amostra_Extra",
    "Condutividade_Eletrica", "Cota_cm", "Cota_de_Mediacao", "Data_Hora_Dado",
    "Data_Hora_Medicao_Liquida", "Data_Ultima_Alteracao", "Largura",
    "Nivel_Consistencia", "Numero_Medicao", "Numero_Medicao_Liquida",
    "Observacoes", "Temperatura_da_Agua", "Vazao_m3_s", "Vel_Media", "codigoestacao",
)


def _carregar_itens(resposta: bytes):
    if not resposta:
        return None
    try:
        conteudo = json.loads(resposta.decode("latin-1"))
    except json.JSONDecodeError:
        return None
    return conteudo.get("items")


def _decodificar_serie_temporal(resposta: bytes, campos: tuple) -> list:
    """Estações telemétricas: cada registro tem hora de medição + campos de série."""
    itens = _carregar_itens(resposta)
    if not itens:
        return [dict.fromkeys(("Hora_Medicao", *campos))]

    registros = []
    for item in itens:
        registro = {"Hora_Medicao": item.get("Data_Hora_Medicao")}
        registro.update({campo: item.get(campo) for campo in campos})
        registros.append(registro)
    return registros


def _decodificar_registro_diario(resposta: bytes, campos: tuple) -> list:
    """Estações convencionais (chuva/cota/sedimento): campos repassados como estão."""
    itens = _carregar_itens(resposta)
    if not itens:
        return [dict.fromkeys(campos)]

    return [{campo: item.get(campo) for campo in campos} for item in itens]


_DECODIFICADORES = {
    "Adotada": lambda resposta: _decodificar_serie_temporal(resposta, CAMPOS_ADOTADA),
    "Detalhada": lambda resposta: _decodificar_serie_temporal(resposta, CAMPOS_DETALHADA),
    "Chuva": lambda resposta: _decodificar_registro_diario(resposta, CAMPOS_CHUVA),
    "Cota": lambda resposta: _decodificar_registro_diario(resposta, CAMPOS_COTA),
    "Sedimento": lambda resposta: _decodificar_registro_diario(resposta, CAMPOS_SEDIMENTO),
}


def decode_respostas(respostas: list, tipo: str) -> list:
    """Decodifica uma lista de respostas brutas (bytes) da API para o tipo informado.

    Args:
        respostas: lista de conteúdos brutos (bytes) retornados pela API.
        tipo: um de 'Adotada', 'Detalhada', 'Chuva', 'Cota', 'Sedimento'.

    Returns:
        Lista de dicionários, um por registro retornado pela API.
    """
    decodificador = _DECODIFICADORES.get(tipo)
    if decodificador is None:
        raise TipoDadoInvalidoError(f"Tipo de dado desconhecido: {tipo!r}.")

    resultado = []
    for resposta in respostas:
        resultado.extend(decodificador(resposta))
    return resultado