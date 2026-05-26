"""Production cost estimates for local and API-assisted media jobs."""

from __future__ import annotations


def estimate_clip_cost(duration_ms: int, llm_provider: str = "none", caption_source: str = "whisper", renderer: str = "hyperframes") -> dict[str, float | str]:
    minutes = max(0.01, duration_ms / 60_000)
    llm_cost = {
        "none": 0.0,
        "deepseek": 0.003,
        "groq": 0.006,
        "openai": 0.012,
    }.get(llm_provider, 0.0)
    local_compute = round(minutes * 0.003, 4)
    cloud_asr = 0.0 if caption_source in {"whisper", "hybrid", "youtube"} else round(minutes * 0.006, 4)
    render_rate = {"remotion": 0.004, "hyperframes": 0.0045, "ffmpeg": 0.002}.get(renderer, 0.002)
    render_compute = round(minutes * render_rate, 4)
    total = round(llm_cost + local_compute + cloud_asr + render_compute, 4)
    return {
        "currency": "USD",
        "llm_provider": llm_provider,
        "caption_source": caption_source,
        "renderer": renderer,
        "llm_cost": llm_cost,
        "local_compute_estimate": local_compute,
        "cloud_asr_cost": cloud_asr,
        "render_compute_estimate": render_compute,
        "estimated_total": total,
    }
