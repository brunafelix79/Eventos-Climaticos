"""hidroaccess: cliente Python para a API HidroWebService da ANA."""

from .client import Access
from .exceptions import (
    DataInvalidaError,
    HidroAccessError,
    TipoDadoInvalidoError,
    TokenInvalidoError,
)

__version__ = "2.0.0"

__all__ = [
    "Access",
    "HidroAccessError",
    "TokenInvalidoError",
    "DataInvalidaError",
    "TipoDadoInvalidoError",
]
