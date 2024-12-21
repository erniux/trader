# dashboard/tests/test_redis_service.py

from django.test import TestCase
from unittest.mock import patch
from decimal import Decimal
from dashboard.utils.redis_service import get_price_from_redis

class RedisServiceTests(TestCase):
    @patch('dashboard.utils.redis_service.redis.Redis.get')
    def test_get_price_from_redis_success(self, mock_redis_get):
        """
        Testea que get_price_from_redis devuelve el precio correctamente cuando Redis responde exitosamente.
        """
        mock_redis_get.return_value = b'50000.0'

        price = get_price_from_redis('BTCUSDT')
        self.assertEqual(price, Decimal('50000.0'))

    @patch('dashboard.utils.redis_service.redis.Redis.get')
    def test_get_price_from_redis_missing(self, mock_redis_get):
        """
        Testea que get_price_from_redis devuelve None cuando el precio no está en Redis.
        """
        mock_redis_get.return_value = None

        price = get_price_from_redis('BTCUSDT')
        self.assertIsNone(price)

    @patch('dashboard.utils.redis_service.redis.Redis.get')
    def test_get_price_from_redis_invalid_price(self, mock_redis_get):
        """
        Testea que get_price_from_redis maneja correctamente un precio inválido en Redis.
        """
        mock_redis_get.return_value = b'invalid_price'

        price = get_price_from_redis('BTCUSDT')
        self.assertIsNone(price)

    @patch('dashboard.utils.redis_service.redis.Redis.get')
    def test_get_price_from_redis_exception(self, mock_redis_get):
        """
        Testea que get_price_from_redis maneja correctamente una excepción durante la obtención del precio.
        """
        mock_redis_get.side_effect = Exception("Redis Error")

        price = get_price_from_redis('BTCUSDT')
        self.assertIsNone(price)
