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
  meta?: {batch_id?: string; batch_formats?: string[]};
};

export type ContentPackageCreateBatchResult = {
  batch_id?: string;
  packages: ContentPackageCreateResult[];
  errors?: {format: string; error: string}[];
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
  formats: string[];
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
  onCreate: (payload: ContentPackageCreatePayload) => Promise<ContentPackageCreateBatchResult>;
  onCreated: (batch: ContentPackageCreateBatchResult) => void;
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
  const [selectedFormats, setSelectedFormats] = useState<string[]>(["text_only"]);
  const [sourceKind, setSourceKind] = useState("youtube");
  const [sourceRef, setSourceRef] = useState("");
  const [topic, setTopic] = useState("");
  const [brandPreset, setBrandPreset] = useState("blank");
  const [job, setJob] = useState("inform");
  const [llmProvider, setLlmProvider] = useState("deepseek");
  const [parentPackageId, setParentPackageId] = useState("");
  const [lastBatch, setLastBatch] = useState<ContentPackageCreateBatchResult | null>(null);
  const [error, setError] = useState("");

  const busy = actionState?.status === "running";
  const sourceLabel =
    sourceKind === "youtube" ? "YouTube URL" : sourceKind === "chat" ? "Chat transcript" : "Topic text";
  const hasParent = Boolean(parentPackageId.trim());

  function toggleFormat(value: string) {
    if (value === "clip" && !hasParent) return;
    setSelectedFormats((current) => {
      if (current.includes(value)) {
        const next = current.filter((f) => f !== value);
        return next.length ? next : ["text_only"];
      }
      return [...current, value];
    });
  }

  async function handleSubmit() {
    setError("");
    setLastBatch(null);
    const ref = sourceRef.trim();
    const topicText = topic.trim();
    const formats = [...selectedFormats];
    const needsSource = formats.some((f) => f !== "clip");
    if (needsSource && !ref && !topicText) {
      setError("Source URL, chat text, or topic is required.");
      return;
    }
    if (formats.includes("clip") && !hasParent) {
      setError("Clip format requires a parent package id.");
      return;
    }
    try {
      const created = await onCreate({
        profile_id: profileId,
        formats,
        source_kind: sourceKind,
        source_ref: ref,
        topic: topicText,
        brand_preset: brandPreset,
        job,
        llm_provider: llmProvider,
        parent_package_id: parentPackageId.trim(),
      });
      setLastBatch(created);
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
        Build publish-ready packages from one source. Select multiple outputs — each becomes its own row in Review → Content
        packages (shared batch id).
      </p>

      <div className="mt-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Outputs</p>
        <div className="mt-2 flex flex-wrap gap-2">
          {FORMATS.map((opt) => {
            const active = selectedFormats.includes(opt.value);
            const clipLocked = opt.value === "clip" && !hasParent;
            return (
              <button
                key={opt.value}
                type="button"
                disabled={clipLocked}
                onClick={() => toggleFormat(opt.value)}
                className={`rounded-full border px-3 py-1.5 text-xs font-semibold transition ${
                  active
                    ? "border-violet-400/60 bg-violet-500/20 text-violet-100"
                    : clipLocked
                      ? "cursor-not-allowed border-white/[0.06] bg-zinc-900/40 text-zinc-600"
                      : "border-white/[0.10] bg-black/20 text-zinc-400 hover:border-white/[0.18] hover:text-zinc-200"
                }`}
                aria-pressed={active}
              >
                {opt.label}
              </button>
            );
          })}
        </div>
        <p className="mt-1.5 text-[11px] text-zinc-600">Default: text only. Clip unlocks when parent package id is set.</p>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
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

      <label className="mt-3 block text-xs font-semibold uppercase tracking-wide text-zinc-500">
        Parent package id (for clip)
        <input
          value={parentPackageId}
          onChange={(e) => setParentPackageId(e.target.value)}
          className="mt-1.5 w-full rounded-2xl border border-white/[0.08] bg-black/30 px-3 py-2 font-mono text-sm text-zinc-100 outline-none focus:border-cyan/40"
        />
      </label>

      {error ? <p className="mt-3 text-xs text-danger">{error}</p> : null}

      {lastBatch?.packages?.length ? (
        <div className="mt-3 rounded-2xl border border-success/25 bg-success/[0.06] p-3 text-xs text-zinc-300">
          {lastBatch.batch_id ? (
            <p className="font-mono text-zinc-500">Batch {lastBatch.batch_id}</p>
          ) : null}
          <ul className="mt-2 space-y-1">
            {lastBatch.packages.map((pkg) => (
              <li key={pkg.id}>
                <span className="font-mono text-success">{pkg.id}</span> · {pkg.format} · {pkg.status}
                {pkg.qa?.passed ? " · QA passed" : ""}
              </li>
            ))}
          </ul>
          {lastBatch.errors?.length ? (
            <p className="mt-2 text-amber-300/90">
              Partial errors: {lastBatch.errors.map((e) => `${e.format}: ${e.error}`).join("; ")}
            </p>
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
        Create {selectedFormats.length > 1 ? `${selectedFormats.length} packages` : "package"}
      </button>
    </details>
  );
}
