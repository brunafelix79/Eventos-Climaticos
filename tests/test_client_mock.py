"""Testes de Access usando mocks — não fazem chamadas reais à API."""

from unittest.mock import MagicMock, patch

import pytest

from hidroaccess.client import Access
from hidroaccess.exceptions import TipoDadoInvalidoError, TokenInvalidoError


def _resposta_mock(status_code, conteudo=b""):
    resposta = MagicMock()
    resposta.status_code = status_code
    resposta.content = conteudo
    return resposta


def test_safe_request_token_credenciais_invalidas():
    sessao = Access("id", "senha")
    with patch.object(sessao, "requisitar_token", return_value=_resposta_mock(401)):
        assert sessao.safe_request_token() == "-1"


def test_safe_request_token_sucesso():
    sessao = Access("id", "senha")
    conteudo = b'{"items": {"tokenautenticacao": "abc123"}}'
    with patch.object(sessao, "requisitar_token", return_value=_resposta_mock(200, conteudo)):
        assert sessao.safe_request_token() == "abc123"


def test_safe_request_token_desiste_apos_max_tentativas():
    sessao = Access("id", "senha")
    with patch.object(sessao, "requisitar_token", return_value=_resposta_mock(500)):
        assert sessao.safe_request_token(tentativas_maximas=3) == "-1"


def test_cabecalho_autenticacao_token_invalido():
    with pytest.raises(TokenInvalidoError, match="Token inválido: -1"):
        Access._cabecalho_autenticacao("-1")


def test_cabecalho_autenticacao_token_valido():
    assert Access._cabecalho_autenticacao("abc") == {"Authorization": "Bearer abc"}


def test_atualizar_credenciais():
    sessao = Access("id_antigo", "senha_antiga")
    sessao.atualizar_credenciais("id_novo", "senha_nova")
    assert sessao._id == "id_novo"
    assert sessao._senha == "senha_nova"


def test_request_telemetrica_tipo_invalido():
    sessao = Access("id", "senha")
    with pytest.raises(TipoDadoInvalidoError):
        sessao.request_telemetrica(85900000, "2020-01-01", "2020-01-02", "token", tipo="Errado")
