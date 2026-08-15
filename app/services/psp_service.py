"""
Simulates what would normally be a network call to a real payment gateway
(Razorpay, Stripe, PayU, etc). No real gateway is involved anywhere here.

We use the PSP's configured success_rate to decide (randomly) whether this
attempt succeeds, and avg_latency_ms to fake a bit of processing delay so the
dashboard "processing_time_ms" numbers look realistic.
"""

import random
import time


def call_psp(psp_name: str, success_rate: float, avg_latency_ms: int) -> dict:
    """
    Simulate sending a payment to a PSP.

    Returns a dict: {"success": bool, "latency_ms": int}
    """
    # add a little jitter around the configured average latency so every
    # call doesn't take exactly the same time
    jitter = random.randint(-50, 50)
    simulated_latency_ms = max(50, avg_latency_ms + jitter)

    # sleep a scaled-down version of the latency so demo requests stay fast,
    # while still feeling like something is actually happening
    time.sleep(simulated_latency_ms / 1000 / 4)

    success = random.random() < success_rate

    return {
        "success": success,
        "latency_ms": simulated_latency_ms,
    }
