import type {ClipCandidate} from "@/lib/media-api";

export type QaPipelineLine = {
  label: string;
  value: string;
  tone: "ok" | "warn" | "muted";
};

function record(value: unknown): Record<string, unknown> | undefined {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : undefined;
}

function titleSourceLabel(source: string) {
  if (source.startsWith("llm")) return "LLM";
  if (source === "heuristic_span") return "heuristic";
  return source || "unknown";
}

export function qaCaptionPipelineLines(clip: ClipCandidate): QaPipelineLine[] {
  const curation = record(clip.curation_metadata) || {};
  const cost = clip.cost || {};
  const corrections = clip.caption_corrections || {};
  const asr = record(clip.asr_metadata) || {};
  const asrPipeline = record(asr.caption_pipeline) || {};
  const llmMeta =
    record(corrections.llm)
    || record(record(corrections.ai_polish_pipeline)?.llm)
    || record(asrPipeline.llm);

  const provider = String(curation.llm_provider || cost.llm_provider || "none");
  const providerLabel = provider === "none" ? "None" : provider.charAt(0).toUpperCase() + provider.slice(1);

  const lines: QaPipelineLine[] = [
    {
      label: "Writing model (job)",
      value: providerLabel,
      tone: provider === "none" ? "muted" : "ok",
    },
  ];

  const llmUsed = curation.llm_used === true;
  const titleSource = String(curation.title_source || "");
  if (provider === "none") {
    lines.push({label: "Clip curation", value: "No LLM — heuristic only", tone: "muted"});
  } else if (llmUsed) {
    lines.push({label: "Clip curation", value: "LLM suggested hook & window", tone: "ok"});
  } else {
    lines.push({
      label: "Clip curation",
      value: `LLM not applied — ${titleSourceLabel(titleSource)} fallback`,
      tone: "warn",
    });
  }

  if (titleSource) {
    lines.push({
      label: "Title / hook source",
      value: titleSourceLabel(titleSource),
      tone: titleSource.startsWith("llm") ? "ok" : "warn",
    });
  }

  let reconstruct = "Not run";
  let reconstructTone: QaPipelineLine["tone"] = "muted";
  if (llmMeta?.llm_reconstructed === true) {
    reconstruct = "Applied to timed captions";
    reconstructTone = "ok";
  } else if (llmMeta?.llm_rejected_ungrounded === true) {
    reconstruct = "Rejected — kept ASR (ungrounded text)";
    reconstructTone = "warn";
  } else if (llmMeta?.llm_error === true) {
    reconstruct = "API error — kept ASR / YouTube text";
    reconstructTone = "warn";
  } else if (llmMeta?.llm_skipped === true) {
    reconstruct = "Skipped (provider none)";
    reconstructTone = "muted";
  } else if (provider !== "none" && clip.caption_source && clip.caption_source !== "youtube") {
    reconstruct = "No LLM reconstruct metadata";
    reconstructTone = "warn";
  }
  lines.push({label: "Caption LLM reconstruct", value: reconstruct, tone: reconstructTone});

  if (corrections.ai_polish) {
    lines.push({
      label: "Review AI polish",
      value: "Applied in editor",
      tone: corrections.manual_edit ? "warn" : "ok",
    });
  }
  if (corrections.manual_edit) {
    lines.push({label: "Caption edits", value: "Manual edits saved", tone: "ok"});
  }

  const captionSource = String(clip.caption_source || cost.caption_source || "—");
  lines.push({label: "Caption source", value: captionSource, tone: "muted"});

  const asrEngine = String(asr.engine || "faster-whisper");
  const asrModel = String(asr.model || "—");
  const detected = String(asr.detected_language || asr.language || corrections.detected_language || "—");
  lines.push({
    label: "ASR",
    value: `${asrEngine} · ${asrModel} · detected ${detected}`,
    tone: "muted",
  });

  const yt = record(corrections.youtube) || record(asrPipeline.youtube);
  if (yt?.used === true || Number(yt?.youtube_replaced) > 0) {
    const replaced = Number(yt.youtube_replaced || 0);
    lines.push({
      label: "YouTube transcript",
      value: replaced ? `Hybrid — ${replaced} word(s) from YT` : "Hybrid — aligned",
      tone: "muted",
    });
  }

  if (typeof cost.llm_cost === "number" && cost.llm_cost > 0) {
    lines.push({
      label: "Job cost field",
      value: `~$${cost.llm_cost.toFixed(3)} llm_cost is an estimate, not provider billing`,
      tone: "warn",
    });
  }

  return lines;
}

export function qaCaptionPipelineSummary(clip: ClipCandidate): string | null {
  const lines = qaCaptionPipelineLines(clip);
  const provider = String(clip.curation_metadata?.llm_provider || clip.cost?.llm_provider || "");
  if (!provider || provider === "none") return null;
  const curation = clip.curation_metadata?.llm_used === true;
  const llmMeta = record(clip.caption_corrections?.llm);
  const reconstructOk = llmMeta?.llm_reconstructed === true;
  if (curation && reconstructOk) return null;
  if (!curation && !reconstructOk) {
    return "This clip was generated with a writing model selected, but no successful OpenAI/DeepSeek/Groq calls were recorded. Hooks and captions came from heuristics and local Whisper.";
  }
  if (!curation) {
    return "Writing model was selected for the job, but clip curation did not use LLM output.";
  }
  return "Writing model ran for curation, but caption reconstruct did not complete successfully.";
}
