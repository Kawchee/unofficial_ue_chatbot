"""
scripts/benchmark_ttft.py

Misura la latenza reale di ogni step della pipeline RAG.
Lancia 4 query in italiano × 3 ripetizioni = 12 chiamate totali.
Produce report a console e CSV in data/diagnostics/.

Uso (dalla root del progetto, con venv attivo):
    python scripts/benchmark_ttft.py

NON avviare il server FastAPI — questo script chiama la pipeline direttamente.
"""

import sys
import os
import csv
import statistics
import time
from datetime import datetime
from pathlib import Path

# Aggiunge la root del progetto al path per permettere gli import da src/
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.api.pipeline import answer

# ---------------------------------------------------------------------------
# Configurazione
# ---------------------------------------------------------------------------

QUERIES_IT = [
    "Quante ore posso lavorare al giorno?",
    "Cosa devo fare se mi ammalo?",
    "Come funziona il pagamento delle ferie?",
    "Chi devo contattare se ho un problema con l'app?",
]

REPETITIONS = 3

# Step da misurare nell'ordine in cui appaiono nella pipeline
STEP_ORDER = [
    "detect_and_translate",
    "rewrite_query",
    "embed_query",
    "vector_search_db",
    "fts_search_db",
    "rerank",
    "llm_call_total",
]

# Nomi leggibili per il report
STEP_LABELS = {
    "detect_and_translate": "1. detect_and_translate (Qwen via OpenRouter)",
    "rewrite_query":        "2. rewrite_query        (no-op: history vuota)",
    "embed_query":          "3. embed_query          (OpenAI text-embedding-3-small)",
    "vector_search_db":     "4. vector_search        (Supabase pgvector)",
    "fts_search_db":        "5. fts_search           (Supabase FTS)",
    "rerank":               "6. rerank               (Cohere Rerank 3.5)",
    "llm_call_total":       "7. llm_call_total       (Qwen via OpenRouter — risposta completa)",
}

OUTPUT_DIR = Path("data/diagnostics")

# ---------------------------------------------------------------------------
# Funzioni di supporto
# ---------------------------------------------------------------------------

def format_seconds(s: float) -> str:
    return f"{s:.3f}s"


def run_query(query: str) -> dict:
    """
    Lancia una singola query e restituisce il dizionario dei tempi per step.
    """
    messages = [{"role": "user", "content": query}]
    timing_collector = {}
    answer(messages, top_k=5, timing_collector=timing_collector)
    return timing_collector


def warmup():
    """
    Query di warmup scartata: apre le connessioni HTTP e riscalda i client.
    """
    print("  [warmup] Lancio query di riscaldamento (risultati scartati)...")
    try:
        run_query("test warmup query")
    except Exception as e:
        print(f"  [warmup] Attenzione: warmup fallito ({e}). Continuo comunque.")
    print("  [warmup] Completato.\n")


def aggregate(timings_per_run: list[dict]) -> dict:
    """
    Dato un elenco di dict {step: seconds}, restituisce per ogni step
    {min, median, max} in secondi.
    """
    all_steps = set()
    for t in timings_per_run:
        all_steps.update(t.keys())

    result = {}
    for step in all_steps:
        values = [t[step] for t in timings_per_run if step in t]
        if values:
            result[step] = {
                "min": min(values),
                "median": statistics.median(values),
                "max": max(values),
                "values": values
            }

    return result


def compute_ttft_per_run(timing: dict) -> float:
    """
    TTFT = somma di tutti gli step escluso llm_call_total
    (che misura la risposta completa, non il primo token).

    Nota: in questa pipeline non c'è streaming nel benchmark — call_llm()
    è bloccante e restituisce la risposta completa. Il "TTFT" misurato qui
    è quindi il tempo prima che call_llm() inizi, che è esattamente il tempo
    che l'utente percepisce prima di vedere qualcosa (nel contesto streaming
    reale, call_llm è sostituito dallo stream SSE e il primo token arriva
    subito dopo l'apertura della connessione).
    """
    pre_llm_steps = [s for s in STEP_ORDER if s != "llm_call_total"]
    return sum(timing.get(s, 0.0) for s in pre_llm_steps)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 70)
    print("BENCHMARK TTFT — Pipeline RAG Uber Eats")
    print(f"Query: {len(QUERIES_IT)} | Ripetizioni: {REPETITIONS} | Totale chiamate: {len(QUERIES_IT) * REPETITIONS}")
    print("=" * 70)
    print()

    # Warmup
    warmup()

    # Raccolta dati
    # Struttura: { query_text: [timing_dict_run1, timing_dict_run2, ...] }
    all_results = {}

    for q_idx, query in enumerate(QUERIES_IT, 1):
        print(f"Query {q_idx}/{len(QUERIES_IT)}: \"{query}\"")
        timings = []

        for rep in range(1, REPETITIONS + 1):
            print(f"  Ripetizione {rep}/{REPETITIONS}...", end=" ", flush=True)
            t_start = time.perf_counter()
            try:
                timing = run_query(query)
                elapsed = time.perf_counter() - t_start
                timings.append(timing)
                print(f"OK ({elapsed:.1f}s totale)")
            except Exception as e:
                elapsed = time.perf_counter() - t_start
                print(f"ERRORE: {e}")

        all_results[query] = timings
        print()

    # ---------------------------------------------------------------------------
    # Report aggregato su tutte le query
    # ---------------------------------------------------------------------------

    # Appiattisce tutti i timing in un'unica lista per aggregazione globale
    all_timings_flat = []
    for timings in all_results.values():
        all_timings_flat.extend(timings)

    agg = aggregate(all_timings_flat)

    # Calcola TTFT per ogni run
    ttft_values = [compute_ttft_per_run(t) for t in all_timings_flat]
    total_values = [sum(t.values()) for t in all_timings_flat]

    print("=" * 70)
    print("REPORT AGGREGATO (tutte le query, tutte le ripetizioni)")
    print("=" * 70)
    print()

    # Header
    print(f"{'Step':<52} {'min':>7} {'median':>8} {'max':>7}  {'% TTFT':>7}")
    print("-" * 85)

    ttft_median = statistics.median(ttft_values) if ttft_values else 0

    for step in STEP_ORDER:
        if step not in agg:
            continue
        data = agg[step]
        label = STEP_LABELS.get(step, step)

        if step == "llm_call_total":
            pct = "—"
        else:
            pct = f"{(data['median'] / ttft_median * 100):.1f}%" if ttft_median > 0 else "—"

        print(
            f"{label:<52} "
            f"{format_seconds(data['min']):>7} "
            f"{format_seconds(data['median']):>8} "
            f"{format_seconds(data['max']):>7}  "
            f"{pct:>7}"
        )

    print("-" * 85)

    ttft_min = min(ttft_values) if ttft_values else 0
    ttft_max = max(ttft_values) if ttft_values else 0
    ttft_med = statistics.median(ttft_values) if ttft_values else 0
    total_med = statistics.median(total_values) if total_values else 0

    print(
        f"{'TTFT (pre-LLM)':<52} "
        f"{format_seconds(ttft_min):>7} "
        f"{format_seconds(ttft_med):>8} "
        f"{format_seconds(ttft_max):>7}  "
        f"{'100%':>7}"
    )
    print(
        f"{'TOTALE (incluso llm_call_total)':<52} "
        f"{'—':>7} "
        f"{format_seconds(total_med):>8} "
        f"{'—':>7}  "
        f"{'—':>7}"
    )
    print()

    # ---------------------------------------------------------------------------
    # Report per singola query
    # ---------------------------------------------------------------------------
    print("=" * 70)
    print("DETTAGLIO PER QUERY (mediana su ripetizioni)")
    print("=" * 70)

    for query, timings in all_results.items():
        if not timings:
            print(f"\n  \"{query}\" — nessun dato (tutte le run hanno fallito)")
            continue

        q_agg = aggregate(timings)
        q_ttft = statistics.median([compute_ttft_per_run(t) for t in timings])
        print(f"\n  \"{query}\"")
        for step in STEP_ORDER:
            if step in q_agg:
                d = q_agg[step]
                print(f"    {step:<35} {format_seconds(d['median'])}")
        print(f"    {'TTFT':<35} {format_seconds(q_ttft)}")

    # ---------------------------------------------------------------------------
    # Salvataggio CSV
    # ---------------------------------------------------------------------------
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = OUTPUT_DIR / f"ttft_{timestamp}.csv"

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["query", "repetition"] + STEP_ORDER + ["ttft_pre_llm", "total"])

        for query, timings in all_results.items():
            for rep_idx, timing in enumerate(timings, 1):
                row = [query, rep_idx]
                for step in STEP_ORDER:
                    row.append(f"{timing.get(step, ''):.4f}" if step in timing else "")
                ttft = compute_ttft_per_run(timing)
                total = sum(timing.values())
                row.append(f"{ttft:.4f}")
                row.append(f"{total:.4f}")
                writer.writerow(row)

    print()
    print(f"CSV salvato in: {csv_path}")
    print()
    print("Benchmark completato.")


if __name__ == "__main__":
    main()
