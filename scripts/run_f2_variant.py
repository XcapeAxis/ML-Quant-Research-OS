"""Run F2.1 variant experiment directly, bypassing the heavy CLI import chain."""
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

start = time.time()
print("[variant_runner] Starting F2.1 variant A2 train...", flush=True)

from quant_mvp.f2_pipeline import run_f2_train

try:
    result = run_f2_train("as_share_research_v1")
    elapsed = time.time() - start
    print(f"\n[variant_runner] Completed in {elapsed:.1f}s", flush=True)
    print(f"[variant_runner] experiment_id: {result['experiment_id']}", flush=True)
    metrics = result.get("topk_metrics", {})
    print(f"[variant_runner] annualized_return: {metrics.get('annualized_return', 'N/A')}", flush=True)
    print(f"[variant_runner] max_drawdown: {metrics.get('max_drawdown', 'N/A')}", flush=True)
    print(f"[variant_runner] sharpe_ratio: {metrics.get('sharpe_ratio', 'N/A')}", flush=True)
    print(f"[variant_runner] calmar_ratio: {metrics.get('calmar_ratio', 'N/A')}", flush=True)
except Exception as e:
    elapsed = time.time() - start
    print(f"\n[variant_runner] FAILED after {elapsed:.1f}s: {e}", flush=True)
    import traceback
    traceback.print_exc()
