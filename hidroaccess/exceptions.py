"""Exceções customizadas da biblioteca hidroaccess."""


class HidroAccessError(Exception):
    """Erro base de toda a biblioteca."""


class TokenInvalidoError(HidroAccessError):
    """Levantado ao tentar usar um token de autenticação inválido ('-1')."""


class DataInvalidaError(HidroAccessError, ValueError):
    """Levantado quando uma data informada não está no formato 'YYYY-MM-DD'."""


class TipoDadoInvalidoError(HidroAccessError, ValueError):
    """Levantado quando um tipo de dado/estação desconhecido é solicitado."""
