# dashboard/tests/test_binance_service.py

from django.test import TestCase
from unittest.mock import patch
from dashboard.utils.binance_service import get_all_tickers

class BinanceServiceTests(TestCase):
    @patch('dashboard.utils.binance_service.Client.get_ticker')
    def test_get_all_tickers_success(self, mock_get_ticker):
        """
        Testea que get_all_tickers devuelve los tickers correctamente cuando la API responde exitosamente.
        """
        mock_tickers = [
            {'symbol': 'BTCUSDT', 'lastPrice': '50000', 'volume': '1234'},
            {'symbol': 'ETHUSDT', 'lastPrice': '4000', 'volume': '5678'},
        ]
        mock_get_ticker.return_value = mock_tickers

        tickers = get_all_tickers()
        self.assertEqual(tickers, mock_tickers)

    @patch('dashboard.utils.binance_service.Client.get_ticker')
    def test_get_all_tickers_failure(self, mock_get_ticker):
        """
        Testea que get_all_tickers maneja correctamente una excepción de la API.
        """
        mock_get_ticker.side_effect = Exception("API Error")

        tickers = get_all_tickers()
        self.assertEqual(tickers, [])
