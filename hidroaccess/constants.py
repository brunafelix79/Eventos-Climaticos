"""Constantes da API HidroWebService (ANA)."""

BASE_URL = "https://www.ana.gov.br/hidrowebservice/EstacoesTelemetricas"

TOKEN_ENDPOINT = f"{BASE_URL}/OAUth/v1"

TELEMETRICA_ENDPOINTS = {
    "Adotada": f"{BASE_URL}/HidroinfoanaSerieTelemetricaAdotada/v1",
    "Detalhada": f"{BASE_URL}/HidroinfoanaSerieTelemetricaDetalhada/v1",
}

CONVENCIONAL_ENDPOINTS = {
    "Sedimento": f"{BASE_URL}/HidroSerieSedimentos/v1",
    "Chuva": f"{BASE_URL}/HidroSerieChuva/v1",
    "Cota": f"{BASE_URL}/HidroSerieCotas/v1",
}

# Maior período (em dias) aceito por uma única requisição de estação convencional.
MAX_DIAS_CONVENCIONAL = 366

TOKEN_INVALIDO = "-1"
