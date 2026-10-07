"use client";

import {ChevronDown, Loader2, Package, Sparkles} from "lucide-react";
import {useState} from "react";

type ActionUiState = {status: "running" | "done" | "failed"; message: string};

const FORMATS = [
  {value: "text_only", label: "Text only"},
  {value: "still", label: "Still image"},
  {value: "carousel", label: "Carousel (3–5 slides)"},
  {value: "short", label: "Short video"},
  {value: "long_form", label: "Long-form video"},
  {value: "clip", label: "Clip (from parent)"},
] as const;

const SOURCE_KINDS = [
  {value: "youtube", label: "YouTube URL"},
  {value: "chat", label: "Chat paste"},
  {value: "topic", label: "Topic / brief"},
] as const;

const BRAND_PRESETS = [
  {value: "blank", label: "Blank"},
  {value: "techtalk", label: "TechTalk"},
  {value: "personal", label: "Personal"},
] as const;

const JOBS = [
  {value: "inform", label: "Inform"},
  {value: "teach", label: "Teach"},
  {value: "save_for_later", label: "Save for later"},
] as const;

const LLM_PROVIDERS = ["none", "deepseek", "openai", "groq", "agent"] as const;

export type ContentPackageCreateResult = {
  id: string;
  format: string;
  status: string;
  caption?: string;
  qa?: {passed?: boolean; errors?: string[]};
};

function SelectField({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: readonly {value: string; label: string}[];
  onChange: (value: string) => void;
}) {
  return (
    <label className="grid gap-1.5 rounded-[22px] border border-white/[0.08] bg-canvas-deep p-3 text-xs font-semibold uppercase tracking-wide text-zinc-500">
      {label}
      <div className="relative flex items-center">
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="w-full cursor-pointer appearance-none bg-transparent pr-8 text-sm font-semibold normal-case tracking-normal text-white outline-none"
        >
          {options.map((opt) => (
            <option key={opt.value} value={opt.value} className="bg-[#17171a] text-white">
              {opt.label}
            </option>
          ))}
        </select>
        <ChevronDown className="pointer-events-none absolute right-1 h-4 w-4 text-zinc-500" aria-hidden />
      </div>
    </label>
  );
}

export type ContentPackageCreatePayload = {
  profile_id: string;
  format: string;
  source_kind: string;
  source_ref: string;
  topic: string;
  brand_preset: string;
  job: string;
  llm_provider: string;
  parent_package_id: string;
};

export type ContentPackageCreateSectionProps = {
  profileId: string;
  actionState?: ActionUiState;
  onCreate: (payload: ContentPackageCreatePayload) => Promise<ContentPackageCreateResult>;
  onCreated: (pkg: ContentPackageCreateResult) => void;
  onOpenReview?: () => void;
  onOpenPublish?: () => void;
};

export function ContentPackageCreateSection({
  profileId,
  actionState,
  onCreate,
  onCreated,
  onOpenReview,
  onOpenPublish,
}: ContentPackageCreateSectionProps) {
  const [format, setFormat] = useState("text_only");
  const [sourceKind, setSourceKind] = useState("youtube");
  const [sourceRef, setSourceRef] = useState("");
  const [topic, setTopic] = useState("");
  const [brandPreset, setBrandPreset] = useState("blank");
  const [job, setJob] = useState("inform");
  const [llmProvider, setLlmProvider] = useState("deepseek");
  const [parentPackageId, setParentPackageId] = useState("");
  const [lastResult, setLastResult] = useState<ContentPackageCreateResult | null>(null);
  const [error, setError] = useState("");

  const busy = actionState?.status === "running";
  const sourceLabel =
    sourceKind === "youtube" ? "YouTube URL" : sourceKind === "chat" ? "Chat transcript" : "Topic text";

  async function handleSubmit() {
    setError("");
    setLastResult(null);
    const ref = sourceRef.trim();
    const topicText = topic.trim();
    if (format !== "clip" && !ref && !topicText) {
      setError("Source URL, chat text, or topic is required.");
      return;
    }
    if (format === "clip" && !parentPackageId.trim()) {
      setError("Clip format requires a parent package id.");
      return;
    }
    try {
      const created = await onCreate({
        profile_id: profileId,
        format,
        source_kind: sourceKind,
        source_ref: ref,
        topic: topicText,
        brand_preset: brandPreset,
        job,
        llm_provider: llmProvider,
        parent_package_id: parentPackageId.trim(),
      });
      setLastResult(created);
      onCreated(created);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create failed");
    }
  }

  return (
    <details className="rounded-[28px] border border-white/[0.08] bg-surface/30 p-5" open>
      <summary className="flex cursor-pointer list-none items-center gap-2 text-sm font-semibold text-zinc-200 marker:hidden">
        <Package className="h-4 w-4 text-violet-400" aria-hidden />
        Content package
        <span className="text-xs font-medium text-zinc-600">text · still · carousel · video</span>
      </summary>

      <p className="mt-3 text-xs leading-relaxed text-zinc-500">
        Build a publish-ready package from YouTube, chat paste, or a topic. Results land in Review → Content packages.
      </p>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <SelectField label="Format" value={format} options={FORMATS} onChange={setFormat} />
        <SelectField label="Source" value={sourceKind} options={SOURCE_KINDS} onChange={setSourceKind} />
        <SelectField label="Brand preset" value={brandPreset} options={BRAND_PRESETS} onChange={setBrandPreset} />
        <SelectField label="Job" value={job} options={JOBS} onChange={setJob} />
        <SelectField
          label="Writing model"
          value={llmProvider}
          options={LLM_PROVIDERS.map((p) => ({value: p, label: p}))}
          onChange={setLlmProvider}
        />
      </div>

      {llmProvider === "agent" ? (
        <p className="mt-3 rounded-xl border border-violet-500/25 bg-violet-500/10 px-3 py-2 text-xs text-violet-200">
          Set <code className="text-violet-100">OTONOM_LLM_AGENT_COMMAND</code> in Publish → LLM keys (or vault). The command must read JSON from stdin and print JSON on stdout.
        </p>
      ) : null}

      <label className="mt-3 block text-xs font-semibold uppercase tracking-wide text-zinc-500">
        {sourceLabel}
        <textarea
          value={sourceKind === "topic" ? topic : sourceRef}
          onChange={(e) => (sourceKind === "topic" ? setTopic(e.target.value) : setSourceRef(e.target.value))}
          rows={sourceKind === "chat" ? 6 : 2}
          placeholder={
            sourceKind === "youtube"
              ? "https://youtube.com/watch?v=…"
              : sourceKind === "chat"
                ? "Paste chat transcript…"
                : "One-line topic or brief"
          }
          className="mt-1.5 w-full rounded-2xl border border-white/[0.08] bg-black/30 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-cyan/40"
        />
      </label>

      {sourceKind !== "topic" && (
        <label className="mt-3 block text-xs font-semibold uppercase tracking-wide text-zinc-500">
          Topic (optional)
          <input
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            className="mt-1.5 w-full rounded-2xl border border-white/[0.08] bg-black/30 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-cyan/40"
          />
        </label>
      )}

      {format === "clip" ? (
        <label className="mt-3 block text-xs font-semibold uppercase tracking-wide text-zinc-500">
          Parent package id
          <input
            value={parentPackageId}
            onChange={(e) => setParentPackageId(e.target.value)}
            className="mt-1.5 w-full rounded-2xl border border-white/[0.08] bg-black/30 px-3 py-2 font-mono text-sm text-zinc-100 outline-none focus:border-cyan/40"
          />
        </label>
      ) : null}

      {error ? <p className="mt-3 text-xs text-danger">{error}</p> : null}

      {lastResult ? (
        <div className="mt-3 rounded-2xl border border-success/25 bg-success/[0.06] p-3 text-xs text-zinc-300">
          <p>
            Created <span className="font-mono text-success">{lastResult.id}</span> · {lastResult.status}
            {lastResult.qa?.passed ? " · QA passed" : ""}
          </p>
          {lastResult.qa?.errors?.length ? (
            <p className="mt-2 text-amber-300/90">QA: {lastResult.qa.errors.join("; ")}</p>
          ) : null}
          <div className="mt-2 flex flex-wrap gap-2">
            {onOpenReview ? (
              <button type="button" onClick={onOpenReview} className="text-cyan hover:underline">
                Open Review
              </button>
            ) : null}
            {onOpenPublish && llmProvider === "agent" ? (
              <button type="button" onClick={onOpenPublish} className="text-zinc-400 hover:underline">
                LLM keys (Publish)
              </button>
            ) : null}
          </div>
        </div>
      ) : null}

      <button
        type="button"
        disabled={busy}
        onClick={() => void handleSubmit()}
        className="mt-4 inline-flex h-11 w-full items-center justify-center gap-2 rounded-full bg-violet-600 text-xs font-bold uppercase tracking-wider text-white hover:bg-violet-500 disabled:opacity-50 sm:w-auto sm:px-8"
      >
        {busy ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : <Sparkles className="h-4 w-4" aria-hidden />}
        Create package
      </button>
    </details>
  );
}
