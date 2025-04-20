import numpy as np
from core.analysis.indicators import sma, ma_cross_signals, rsi

def test_sma_basico():
    arr = np.arange(1, 6)  # [1,2,3,4,5]
    expected = np.array([np.nan, np.nan, 2.0, 3.0, 4.0])
    np.testing.assert_allclose(sma(arr, 3), expected, equal_nan=True)


def test_ma_cross_signals():
    prices = np.array([
        1,2,3,4,5,6,7,8,9,10,          # sube
        11,12,13,14,15,16,17,16,15,14, # gira
        13,12,11,10,9,8,7,6,5,4
    ], dtype=float)

    sig = ma_cross_signals(prices, short=3, long=5)

    assert sig["BUY"]  == [4]   # primer punto con ambas SMA y cruce al alza
    assert sig["SELL"] == [19]  # cruce a la baja


def test_rsi_basico():
    """
    Serie sintética: precios suben lineal de 1 a 15, luego bajan a 1.
    RSI 14:
      – Al final del tramo alcista (~índice 14) ≈ 70‑100
      – Al final del tramo bajista (~último índice) ≈ 0‑30
    """
    prices = np.array([1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,
                       14,13,12,11,10,9,8,7,6,5,4,3,2,1], dtype=float)

    rsi_vals = rsi(prices, period=14)

    # último valor bajista debería ser <=30
    assert rsi_vals[-1] <= 30
    # valor alto después de la subida debería ser >=70
    assert rsi_vals[14] >= 70


