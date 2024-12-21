# dashboard/tests/test_arbitrage.py

from django.test import TestCase
from decimal import Decimal
from dashboard.utils.arbitrage import calculate_profit

class ArbitrageCalculationTests(TestCase):
    def test_calculate_profit_positive(self):
        """
        Testea que la función calcula una ganancia positiva correctamente.
        """
        price_a = Decimal('50000')  # BTC/USDT
        price_b = Decimal('4000')   # ETH/USDT
        price_c = Decimal('0.08')   # ETH/BTC

        profit = calculate_profit(price_a, price_b, price_c)
        self.assertGreater(profit, 0)

    def test_calculate_profit_zero(self):
        """
        Testea que la función calcula una ganancia cero correctamente.
        """
        price_a = Decimal('50000')  # BTC/USDT
        price_b = Decimal('4000')   # ETH/USDT
        price_c = Decimal('0.02')   # ETH/BTC (hipotético para no ganar)

        profit = calculate_profit(price_a, price_b, price_c)
        self.assertEqual(profit, Decimal('0'))

    def test_calculate_profit_negative(self):
        """
        Testea que la función calcula una ganancia negativa correctamente.
        """
        price_a = Decimal('50000')  # BTC/USDT
        price_b = Decimal('4000')   # ETH/USDT
        price_c = Decimal('0.015')  # ETH/BTC (hipotético para perder)

        profit = calculate_profit(price_a, price_b, price_c)
        self.assertLess(profit, 0)

    def test_calculate_profit_with_fees_and_slippage(self):
        """
        Testea que la función considera correctamente las tarifas y el slippage.
        """
        price_a = Decimal('50000')   # BTC/USDT
        price_b = Decimal('4000')    # ETH/USDT
        price_c = Decimal('0.08')    # ETH/BTC
        fee_rate = Decimal('0.01')   # 1%
        slippage_rate = Decimal('0.0005')  # 0.05%

        # Calcular manualmente la ganancia esperada
        initial_amount = Decimal('1')
        step1 = initial_amount * price_a  # 50000
        step1_after_fee = step1 * (1 - fee_rate)  # 50000 * 0.99 = 49500
        step1_final = step1_after_fee * (1 - slippage_rate)  # 49500 * 0.9995 = 49475.25

        step2 = step1_final * price_b  # 49475.25 * 4000 = 197901000
        step2_after_fee = step2 * (1 - fee_rate)  # 197901000 * 0.99 = 195921990
        step2_final = step2_after_fee * (1 - slippage_rate)  # 195921990 * 0.9995 = 195822059.005

        step3 = step2_final * price_c  # 195822059.005 * 0.08 = 15665764.7204
        step3_after_fee = step3 * (1 - fee_rate)  # 15665764.7204 * 0.99 = 15509118.0722
        final_amount = step3_after_fee * (1 - slippage_rate)  # 15509118.0722 * 0.9995 = 15501672.0269

        profit_expected = final_amount - initial_amount  # 15501672.0269 - 1 = 15501671.0269

        profit = calculate_profit(price_a, price_b, price_c, fee_rate, slippage_rate)
        self.assertAlmostEqual(profit, profit_expected, places=4)
