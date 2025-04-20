"""
Simple Moving Average (SMA) puro NumPy.
"""
import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

def sma(series: np.ndarray, period: int) -> np.ndarray:
    """
    Devuelve un array del mismo tamaño que `series` con NaN en las
    primeras (`period` - 1) posiciones y el promedio móvil a partir de ahí.

    Parameters
    ----------
    series : np.ndarray
        Vector de precios (float).
    period : int
        Longitud de la ventana.

    Returns
    -------
    np.ndarray
    """
    if period < 1 or period > series.size:
        raise ValueError("period out of bounds")

    window = sliding_window_view(series, window_shape=period)
    sma_vals = window.mean(axis=1)

    # Pre‑pend NaNs para alinear con la serie original
    return np.concatenate([np.full(period - 1, np.nan), sma_vals])
