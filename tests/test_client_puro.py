"""Testes das funções puras (sem rede) do módulo client."""

from datetime import datetime

import pytest

from hidroaccess.client import (
    _janelas_convencional,
    _janelas_telemetrica,
    _tamanho_bloco_telemetrica,
    _validar_data,
)
from hidroaccess.exceptions import DataInvalidaError


def _d(data: str) -> datetime:
    return datetime.strptime(data, "%Y-%m-%d")


@pytest.mark.parametrize("dias_restantes, esperado", [
    (60, 30), (30, 30), (25, 21), (21, 21), (15, 14),
    (14, 14), (10, 7), (7, 7), (5, 2), (2, 2), (1, 1), (0, 1),
])
def test_tamanho_bloco_telemetrica(dias_restantes, esperado):
    assert _tamanho_bloco_telemetrica(dias_restantes) == esperado


@pytest.mark.parametrize("inicio, fim, qtd_dias_esperada", [
    ("2024-01-01", "2024-03-01", 30),
    ("2024-01-01", "2024-01-04", 2),
    ("2024-01-01", "2024-01-02", 1),
    ("2024-01-01", "2024-01-29", 21),
    ("2024-01-01", "2024-01-18", 14),
    ("2024-01-01", "2024-01-08", 7),
])
def test_janelas_telemetrica_primeiro_bloco(inicio, fim, qtd_dias_esperada):
    """O primeiro bloco gerado deve corresponder ao maior intervalo cabível."""
    primeira_janela = next(_janelas_telemetrica(_d(inicio), _d(fim)))
    intervalo_esperado = {
        30: "DIAS_30", 21: "DIAS_21", 14: "DIAS_14",
        7: "DIAS_7", 2: "DIAS_2", 1: "HORA_24",
    }[qtd_dias_esperada]
    assert primeira_janela[1] == intervalo_esperado


@pytest.mark.parametrize("inicio, fim, dias_unicos_esperados", [
    ("2024-01-01", "2024-01-03", 2),
    ("2024-01-01", "2024-02-01", 31),
    ("2024-01-01", "2024-02-04", 34),
    ("2024-01-01", "2024-01-06", 5),
    ("2024-01-01", "2024-01-23", 22),
    ("2024-01-01", "2024-01-18", 17),
])
def test_janelas_telemetrica_cobre_todos_os_dias(inicio, fim, dias_unicos_esperados):
    """A soma dos blocos gerados deve cobrir exatamente o período solicitado."""
    dias_cobertos = set()
    atual = _d(inicio)
    for dia_final_bloco, intervalo in _janelas_telemetrica(_d(inicio), _d(fim)):
        tamanho = {"DIAS_30": 30, "DIAS_21": 21, "DIAS_14": 14,
                   "DIAS_7": 7, "DIAS_2": 2, "HORA_24": 1}[intervalo]
        for offset in range(tamanho):
            dias_cobertos.add(dia_final_bloco.toordinal() - offset)
    assert len(dias_cobertos) == dias_unicos_esperados


def test_janelas_telemetrica_periodo_vazio():
    assert list(_janelas_telemetrica(_d("2024-01-01"), _d("2024-01-01"))) == []


@pytest.mark.parametrize("inicio, fim, fim_primeiro_bloco_esperado", [
    ("2020-01-01", "2024-01-01", "2021-01-01"),
    ("2020-01-01", "2020-01-02", "2020-01-02"),
])
def test_janelas_convencional_respeita_limite_maximo(inicio, fim, fim_primeiro_bloco_esperado):
    primeira_janela = next(_janelas_convencional(_d(inicio), _d(fim)))
    assert primeira_janela == (_d(inicio), _d(fim_primeiro_bloco_esperado))


def test_janelas_convencional_periodo_vazio():
    assert list(_janelas_convencional(_d("2024-01-01"), _d("2024-01-01"))) == []


@pytest.mark.parametrize("data, valida", [
    ("2024-01-01", True),
    ("2024-01-32", False),
    ("2015-02-30", False),
    ("12-12-2024", False),
    ("12/12/12", False),
    ("2024/12/12", False),
])
def test_validar_data(data, valida):
    if valida:
        assert _validar_data(data) == datetime.strptime(data, "%Y-%m-%d")
    else:
        with pytest.raises(DataInvalidaError):
            _validar_data(data)


def test_validar_data_tipo_invalido():
    with pytest.raises(DataInvalidaError):
        _validar_data(12)
