from django.test import TestCase
from dashboard.models import Oportunity, Symbol
from dashboard.tasks import find_and_save_arbitrage_opportunities
from decimal import Decimal


class OportunityModelTest(TestCase):
    def setUp(self):
        self.oportunity = Oportunity.objects.create(
            route="TEST OPORTUNITY",
            symbol_1="BTCUSDT",
            symbol_2="ETHUSDT",
            symbol_3="BTCETH"
        )

    def test_oportunity_model_exists(self):
        oportunity = Oportunity.objects.count()
        self.assertEqual(oportunity, 0)


    def test_oportunity_has_route(self):

        first_oportunity = Oportunity.objects.get(route='TEST OPORTUNITY')
        self.assertEqual(str(first_oportunity), self.oportunity.route)



class ArbitrageTaskTest(TestCase):
    def setUp(self):
        """
        Configuración inicial: crear datos simulados.
        """
        Symbol.objects.create(symbol='BTCUSDT', base_asset='BTC', quote_asset='USDT')
        Symbol.objects.create(symbol='ETHUSDT', base_asset='ETH', quote_asset='USDT')
        Symbol.objects.create(symbol='ETHBTC', base_asset='ETH', quote_asset='BTC')

    def test_find_and_save_arbitrage_opportunities(self):
        """
        Verifica que el task encuentra y guarda oportunidades de arbitraje.
        """
        # Ejecutar el task
        find_and_save_arbitrage_opportunities()

        # Validar que se haya guardado una oportunidad
        self.assertEqual(Oportunity.objects.count(), 1)

        # Validar los detalles de la oportunidad
        opportunity = Oportunity.objects.first()
        self.assertEqual(opportunity.route, 'BTCUSDT -> ETHUSDT -> ETHBTC')
