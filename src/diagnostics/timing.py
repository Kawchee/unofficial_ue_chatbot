"""
src/diagnostics/timing.py

Modulo di misurazione latenza per la pipeline RAG.
Uso: context manager `timed` che accumula misurazioni in un dizionario.

Esempio:
    collector = {}
    with timed("detect_and_translate", collector):
        result = detect_and_translate(query)
    # collector == {"detect_and_translate": 1.23}
"""

import time
from contextlib import contextmanager


@contextmanager
def timed(step_name: str, collector: dict):
    """
    Misura il tempo di esecuzione di un blocco e lo salva in collector.

    Args:
        step_name: chiave con cui salvare la misurazione
        collector: dizionario in cui accumulare i tempi (modificato in-place)
    """
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        collector[step_name] = elapsed
