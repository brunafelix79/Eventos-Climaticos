"""Testes do módulo decoders, usando respostas JSON simuladas."""

import json

import pytest

from hidroaccess.decoders import decode_respostas
from hidroaccess.exceptions import TipoDadoInvalidoError


def _resposta(items):
    return json.dumps({"items": items}).encode("latin-1")


def test_decode_adotada():
    resposta = _resposta([
        {"Data_Hora_Medicao": "2020-01-01 00:00:00", "Chuva_Adotada": 1.0,
         "Cota_Adotada": 100, "Vazao_Adotada": 5.5, "Chuva_Acumulada": 9},
    ])
    resultado = decode_respostas([resposta], "Adotada")
    assert resultado == [{
        "Hora_Medicao": "2020-01-01 00:00:00",
        "Chuva_Adotada": 1.0,
        "Cota_Adotada": 100,
        "Vazao_Adotada": 5.5,
    }]


def test_decode_detalhada_inclui_campos_extras():
    resposta = _resposta([
        {"Data_Hora_Medicao": "2020-01-01 00:00:00", "Chuva_Adotada": 1.0,
         "Cota_Adotada": 100, "Vazao_Adotada": 5.5, "Chuva_Acumulada": 9, "Cota_Sensor": 101},
    ])
    resultado = decode_respostas([resposta], "Detalhada")
    assert set(resultado[0].keys()) == {
        "Hora_Medicao", "Chuva_Acumulada", "Chuva_Adotada", "Cota_Adotada", "Cota_Sensor", "Vazao_Adotada",
    }


def test_decode_sem_itens_retorna_registro_vazio():
    resposta = _resposta(None)
    resultado = decode_respostas([resposta], "Adotada")
    assert len(resultado) == 1
    assert resultado[0] == {
        "Hora_Medicao": None, "Chuva_Adotada": None, "Cota_Adotada": None, "Vazao_Adotada": None,
    }


def test_decode_chuva_chaves_esperadas():
    resposta = _resposta([{"codigoestacao": 47000, "Total": 10}])
    resultado = decode_respostas([resposta], "Chuva")
    chaves_esperadas = {
        "Chuva_01", "Chuva_01_Status", "Chuva_31", "Chuva_31_Status",
        "Data_Hora_Dado", "Data_Ultima_Alteracao", "Dia_Maxima", "Maxima", "Maxima_Status",
        "Nivel_Consistencia", "Numero_Dias_de_Chuva", "Numero_Dias_de_Chuva_Status",
        "Tipo_Medicao_Chuvas", "Total", "Total_Anual", "Total_Anual_Status",
        "Total_Status", "codigoestacao",
    }
    assert chaves_esperadas.issubset(resultado[0].keys())
    assert len(resultado[0]) == 31 * 2 + 14  # 31 dias x (valor+status) + campos fixos


def test_decode_cota_tem_62_campos_numerados_mais_fixos():
    resposta = _resposta([{"codigoestacao": 1}])
    resultado = decode_respostas([resposta], "Cota")
    assert len(resultado[0]) == 31 * 2 + 16


def test_decode_sedimento_chaves_esperadas():
    resposta = _resposta([{"codigoestacao": 72980000, "Vazao_m3_s": 12.3}])
    resultado = decode_respostas([resposta], "Sedimento")
    assert resultado[0]["codigoestacao"] == 72980000
    assert resultado[0]["Vazao_m3_s"] == 12.3
    assert len(resultado[0]) == 18


def test_decode_multiplas_respostas_concatena():
    r1 = _resposta([{"Data_Hora_Medicao": "d1", "Chuva_Adotada": 1, "Cota_Adotada": 2, "Vazao_Adotada": 3}])
    r2 = _resposta([{"Data_Hora_Medicao": "d2", "Chuva_Adotada": 4, "Cota_Adotada": 5, "Vazao_Adotada": 6}])
    resultado = decode_respostas([r1, r2], "Adotada")
    assert [r["Hora_Medicao"] for r in resultado] == ["d1", "d2"]


def test_decode_tipo_invalido():
    with pytest.raises(TipoDadoInvalidoError):
        decode_respostas([_resposta([])], "Inexistente")
