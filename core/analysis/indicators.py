import numpy as np
from numpy.lib.stride_tricks import sliding_window_view


def sma(series: np.ndarray, period: int) -> np.ndarray:
    """
    Simple Moving Average (SMA) puro NumPy.
    Devuelve un array con NaN en los primeros `period-1` valores.
    """
    if period < 1:
        raise ValueError("period must be >= 1")
    if series.size < period:
        # todo NaN: no hay suficientes datos
        return np.full(series.size, np.nan)
    window = sliding_window_view(series, window_shape=period)
    sma_vals = window.mean(axis=1)
    # Prepend NaN para alinear tamaño
    return np.concatenate((np.full(period - 1, np.nan), sma_vals))


def ma_cross_signals(close: np.ndarray, short: int = 9, long: int = 21):
    """
    Cruces de SMA corta y larga.
    Detecta BUY cuando la corta pasa de ≤ a >, incluso si el día anterior
    la SMA larga era NaN (primer punto calculable).
    """
    ma_short = sma(close, short)
    ma_long = sma(close, long)

    buy_idx, sell_idx = [], []
    for i in range(1, len(close)):
        cur_s, cur_l = ma_short[i], ma_long[i]
        prev_s, prev_l = ma_short[i - 1], ma_long[i - 1]

        # saltamos si la media larga aún no existe hoy
        if np.isnan(cur_s) or np.isnan(cur_l):
            continue

        # si ayer faltaba alguna media, tomamos ese “cruce inicial”
        if np.isnan(prev_s) or np.isnan(prev_l):
            if cur_s > cur_l:
                buy_idx.append(i)
            elif cur_s < cur_l:
                sell_idx.append(i)
            continue

        # cruces normales
        if prev_s <= prev_l and cur_s > cur_l:
            buy_idx.append(i)
        elif prev_s >= prev_l and cur_s < cur_l:
            sell_idx.append(i)

    return {"BUY": buy_idx, "SELL": sell_idx}


def _ema(arr: np.ndarray, period: int):
    alpha = 2 / (period + 1)
    ema = np.empty_like(arr, dtype=float)
    ema[:] = np.nan
    for i, val in enumerate(arr):
        if i == 0:
            ema[i] = val
        else:
            if np.isnan(ema[i-1]):
                ema[i] = val
            else:
                ema[i] = val * alpha + ema[i-1] * (1 - alpha)
    return ema


# --- nuevo indicador ---
def rsi(close: np.ndarray, period: int = 14) -> np.ndarray:
    """
    Relative Strength Index (RSI) puro NumPy.
    Devuelve array aligned (primeros `period`-1 NaN).
    """
    delta = np.diff(close, prepend=np.nan)
    gains = np.where(delta > 0, delta, 0.0)
    losses = np.where(delta < 0, -delta, 0.0)

    avg_gain = _ema(gains, period)
    avg_loss = _ema(losses, period)

    rs = np.where(avg_loss == 0, np.inf, avg_gain / avg_loss)
    rsi_vals = 100 - (100 / (1 + rs))
    rsi_vals[:period] = np.nan  # los primeros no son válidos
    return rsi_vals