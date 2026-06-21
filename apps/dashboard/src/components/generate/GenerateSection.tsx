"use client";

import {BadgeCheck, CheckCircle2, ChevronDown, Clapperboard, Copy, Link, Loader2, Sparkles, Wand2, Youtube} from "lucide-react";
import {useState, type Dispatch, type ReactNode, type SetStateAction} from "react";
import {FocusModal} from "@/components/FocusModal";
import {TemplatePreview} from "@/components/templates/TemplatePreview";
import {SlideToConfirm} from "@/components/shared/SlideToConfirm";
import {
  type ActionUiState,
  type BrandTemplate,
  type DurationPreset,
  type EngineHealth,
  type GenerationJob,
  type GenreOption,
  type HyperframesCatalog,
  type HyperframesTemplate,
} from "./types";

type GenerateConfigLike = {
  sourceUrl: string;
  count: number;
  clipLength: string;
  clipMinSeconds: number;
  clipMaxSeconds: number;
  genres: string[];
  renderer: string;
  hyperframesTemplate: string;
  hyperframesFormat: string;
  brandSystemTemplateId: string;
  brandTemplate: string;
  captionSource: string;
  speechLanguage: string;
  transcriptLanguages: string;
  llmProvider: string;
  quality: string;
};

type ReadinessLineComponent = (props: {ready: boolean; label: string; detail: string}) => ReactNode;

type SelectTileOption = string | {value: string; label: string; disabled?: boolean};

export function GenerateSection<T extends GenerateConfigLike>({
  config,
  templates,
  hyperframesTemplates,
  hyperframesCatalog,
  durationPresets,
  genres,
  jobs,
  engineHealth,
  actionState,
  setConfig,
  command,
  defaultTemplatePath,
  statusTone,
  onGenerate,
  onCopy,
  renderReadinessLine,
  renderActionStatus,
  renderEmptyState,
}: {
  config: T;
  templates: BrandTemplate[];
  hyperframesTemplates: HyperframesTemplate[];
  hyperframesCatalog: HyperframesCatalog | null;
  durationPresets: DurationPreset[];
  genres: GenreOption[];
  jobs: GenerationJob[];
  engineHealth: EngineHealth | null;
  actionState?: ActionUiState;
  setConfig: Dispatch<SetStateAction<T>>;
  command: string;
  defaultTemplatePath: string;
  statusTone: (status: string) => string;
  onGenerate: () => void;
  onCopy: () => void;
  renderReadinessLine: ReadinessLineComponent;
  renderActionStatus: (state?: ActionUiState) => ReactNode;
  renderEmptyState: (title: string, text: string) => ReactNode;
}) {
  const latest = jobs[0];
  const isStarting = actionState?.status === "running";
  const [templatePickerOpen, setTemplatePickerOpen] = useState(false);
  const [createStep, setCreateStep] = useState<1 | 2 | 3>(1);
  const update = (patch: Partial<GenerateConfigLike>) => setConfig((current) => ({...current, ...patch}));
  const presetOptions = durationPresets.length ? durationPresets : [{id: "auto", label: "Auto (0-3 min)", detail: "20-180s", range_label: "0-3 min", best_for: "General use", min_ms: 20_000, target_ms: 90_000, max_ms: 180_000, intent: "Automatic duration"}];
  const genreOptions = genres.length ? genres : [
    {id: "kajian", label: "Kajian", description: "Religious teaching and reflection."},
    {id: "spiritual_reflection", label: "Spiritual reflection", description: "Heart-softening clips."},
    {id: "advice", label: "Advice", description: "Practical reminders."},
  ];
  const selectedPreset = presetOptions.find((item) => item.id === config.clipLength) || presetOptions[0];
  const hyperframesReady = Boolean(engineHealth?.hyperframes.ready);
  const hyperframesTemplateOptions = [
    {value: "auto", label: "Auto by niche"},
    ...hyperframesTemplates.map((template) => ({value: template.id, label: template.label})),
  ];
  const selectedTemplate = hyperframesTemplates.find((template) => template.id === config.hyperframesTemplate);
  const productionReadyCount = hyperframesCatalog?.items.filter((item) => item.status === "production-ready").length || 0;
  const latestProgress = Math.max(0, Math.min(100, latest?.progress || 0));
  const selectedGenreCount = genreOptions.filter((genre) => config.genres.includes(genre.id)).length;
  const canContinueFromTemplate = Boolean(selectedTemplate || config.hyperframesTemplate === "auto");
  const canContinueFromSource = Boolean(config.sourceUrl.trim());
  const canOpenStep = (step: 1 | 2 | 3) => {
    if (step === 1) return true;
    if (step === 2) return canContinueFromTemplate;
    return canContinueFromTemplate && canContinueFromSource;
  };
  const stepReady = {
    1: canContinueFromTemplate,
    2: canContinueFromSource,
    3: selectedGenreCount > 0,
  } as const;
  const goNextStep = () => setCreateStep((current) => (current < 3 ? ((current + 1) as 1 | 2 | 3) : current));
  const goPrevStep = () => setCreateStep((current) => (current > 1 ? ((current - 1) as 1 | 2 | 3) : current));
  const toggleGenre = (id: string) => {
    const next = config.genres.includes(id) ? config.genres.filter((item) => item !== id) : [...config.genres, id];
    update({genres: next.length ? next : [id]});
  };

  return (
    <section className="grid min-w-0 gap-5 2xl:grid-cols-[minmax(0,.9fr)_minmax(0,1.1fr)]">
      <div className="min-w-0 rounded-[24px] border border-white/[0.08] bg-surface p-4 sm:rounded-[28px] sm:p-5">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <span className="inline-flex rounded-full border border-teal/[0.22] bg-teal/[0.08] px-3 py-1 text-xs font-semibold text-teal">Template-first flow</span>
            <h3 className="mt-3 text-2xl font-semibold text-white">
              Create <span className="font-editorial italic font-normal text-cyan">clips</span>
            </h3>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-zinc-400">Choose a production template first, then add the source, niche, and output settings for a HyperFrames render.</p>
          </div>
          <div className="grid gap-1 rounded-[20px] border border-white/[0.08] bg-canvas-deep px-4 py-3 text-left sm:min-w-[150px] sm:text-right">
            <span className="text-[11px] font-semibold uppercase tracking-wide text-zinc-500">Batch output</span>
            <span className="text-lg font-semibold text-white">{config.count} clips</span>
            <span className="text-xs text-cyan">{config.clipMinSeconds}s-{config.clipMaxSeconds}s window</span>
          </div>
        </div>

        <div className="mt-6 grid gap-5">
          <div className="grid gap-2 sm:grid-cols-3">
            <StepChip step={1} label="Template" active={createStep === 1} done={stepReady[1]} enabled={canOpenStep(1)} onClick={() => setCreateStep(1)} />
            <StepChip step={2} label="Source" active={createStep === 2} done={stepReady[2]} enabled={canOpenStep(2)} onClick={() => setCreateStep(2)} />
            <StepChip step={3} label="Intent + Run" active={createStep === 3} done={stepReady[3]} enabled={canOpenStep(3)} onClick={() => setCreateStep(3)} />
          </div>
          <div className="rounded-[24px] border border-cyan/[0.18] bg-teal/[0.07] p-4">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <span className="flex h-8 w-8 items-center justify-center rounded-full bg-cyan text-ink">1</span>
                <div>
                  <h4 className="font-semibold text-white">Choose video template</h4>
                  <p className="text-xs text-zinc-500">Template-first generation keeps the render style clear before sourcing clips.</p>
                </div>
              </div>
              <span className="rounded-full border border-cyan/[0.24] bg-black/20 px-3 py-1 text-xs font-semibold text-cyan">HyperFrames primary</span>
            </div>
            <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_170px]">
              <SelectTile
                label="Video template"
                value={config.hyperframesTemplate}
                options={hyperframesTemplateOptions}
                onChange={(value) => {
                  const picked = hyperframesTemplates.find((template) => template.id === value);
                  update({
                    renderer: "hyperframes",
                    hyperframesTemplate: value,
                    brandSystemTemplateId: picked?.source === "brand_system" ? value : "",
                    brandTemplate: picked?.brand_template_path || config.brandTemplate,
                  });
                }}
              />
              <SelectTile
                label="Frame"
                value={config.hyperframesFormat}
                options={[
                  {value: "short_9_16", label: "Short/Reels 9:16"},
                  {value: "long_16_9", label: "Long 16:9"},
                  {value: "auto", label: "Auto"},
                ]}
                onChange={(value) => update({hyperframesFormat: value})}
              />
            </div>
            <button
              type="button"
              onClick={() => setTemplatePickerOpen(true)}
              className="mt-3 inline-flex h-11 w-full items-center justify-center gap-2 rounded-full border border-cyan/[0.24] bg-black/20 px-4 text-sm font-semibold text-cyan transition hover:bg-teal/[0.10] sm:w-fit"
            >
              <Sparkles className="h-4 w-4" />
              Browse visual templates
            </button>
            <div className="mt-3 grid gap-2 text-xs md:grid-cols-3">
              {renderReadinessLine({ready: hyperframesReady, label: "Runtime", detail: hyperframesReady ? "Ready" : "Check required"})}
              {renderReadinessLine({ready: Boolean(selectedTemplate || config.hyperframesTemplate === "auto"), label: "Template", detail: selectedTemplate?.source?.replaceAll("_", " ") || "Auto"})}
              {renderReadinessLine({ready: productionReadyCount > 0, label: "Catalog", detail: `${productionReadyCount} production-ready`})}
            </div>
            {createStep === 1 ? (
              <div className="mt-4 flex justify-end">
                <button type="button" disabled={!stepReady[1]} onClick={goNextStep} className="inline-flex h-10 items-center justify-center rounded-full bg-cyan px-4 text-sm font-semibold text-ink disabled:cursor-not-allowed disabled:opacity-50">
                  Continue to source
                </button>
              </div>
            ) : null}
          </div>

          {createStep >= 2 ? (
            <div className="rounded-[24px] border border-white/[0.08] bg-canvas-deep p-4">
              <div className="mb-4 flex items-center gap-3">
                <span className="flex h-8 w-8 items-center justify-center rounded-full bg-teal/[0.12] text-cyan">2</span>
                <div>
                  <h4 className="font-semibold text-white">Source and output</h4>
                  <p className="text-xs text-zinc-500">Start with the long video and expected batch size.</p>
                </div>
              </div>
              <div className="grid gap-4">
                <div className="grid min-w-0 gap-2 text-sm font-medium text-zinc-300">
                  <span>YouTube source</span>
                  <div className="relative flex items-center">
                    <input
                      value={config.sourceUrl}
                      onChange={(event) => update({sourceUrl: event.target.value})}
                      className="h-12 w-full rounded-full border border-white/[0.08] bg-black/24 pl-11 pr-4 text-sm text-zinc-200 outline-none transition focus:border-cyan/[0.30] focus:ring-1 focus:ring-cyan/[0.30]"
                      placeholder="Paste long-form YouTube URL (https://...)"
                    />
                    <span className="absolute left-4 text-zinc-500">
                      <Youtube className="h-4 w-4" />
                    </span>
                  </div>
                </div>
                <div className="grid min-w-0 gap-4">
                  <div className="grid gap-2 text-sm font-medium text-zinc-300">
                    <span>Clip count</span>
                    <div className="flex flex-wrap gap-1.5">
                      {[1, 2, 3, 5, 8, 10].map((val) => {
                        const active = config.count === val;
                        return (
                          <button
                            key={val}
                            type="button"
                            onClick={() => update({count: val})}
                            className={`h-9 rounded-full px-3.5 text-xs font-semibold transition ${
                              active
                                ? "bg-cyan text-ink shadow-[0_4px_12px_rgba(102,232,249,0.2)]"
                                : "border border-white/[0.08] bg-black/24 text-zinc-400 hover:border-white/[0.16] hover:text-white"
                            }`}
                          >
                            {val} clip{val > 1 ? "s" : ""}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                  <div className="grid gap-2 text-sm font-medium text-zinc-300">
                    <span>Clip duration preset</span>
                    <div className="grid gap-2 sm:grid-cols-2">
                      {presetOptions.map((preset) => {
                        const active = config.clipLength === preset.id;
                        return (
                          <button
                            key={preset.id}
                            type="button"
                            onClick={() => {
                              update({
                                clipLength: preset.id,
                                clipMinSeconds: Math.round(preset.min_ms / 1000),
                                clipMaxSeconds: Math.round(preset.max_ms / 1000),
                              });
                            }}
                            className={`flex flex-col rounded-2xl border p-3 text-left transition ${
                              active
                                ? "border-cyan/[0.50] bg-cyan/[0.05] shadow-[0_4px_12px_rgba(102,232,249,0.06)]"
                                : "border-white/[0.08] bg-black/24 hover:border-white/[0.16]"
                            }`}
                          >
                            <span className={`text-xs font-semibold ${active ? "text-cyan" : "text-white"}`}>{preset.label}</span>
                            <span className="text-[11px] text-zinc-500 mt-1 leading-4">{preset.detail} · {preset.best_for}</span>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                </div>
                <div className="rounded-2xl border border-teal/[0.16] bg-teal/[0.06] px-4 py-3 text-xs leading-5 text-zinc-400">
                  <span className="font-semibold text-cyan">{selectedPreset?.label}</span> lets the engine trim natural starts and endings inside <span className="font-semibold text-zinc-200">{config.clipMinSeconds}s-{config.clipMaxSeconds}s</span>.
                </div>
              </div>
              {createStep === 2 ? (
                <div className="mt-4 flex items-center justify-between gap-3">
                  <button type="button" onClick={goPrevStep} className="inline-flex h-10 items-center justify-center rounded-full border border-white/[0.12] bg-black/20 px-4 text-sm font-semibold text-zinc-200">
                    Back
                  </button>
                  <button type="button" disabled={!stepReady[2]} onClick={goNextStep} className="inline-flex h-10 items-center justify-center rounded-full bg-cyan px-4 text-sm font-semibold text-ink disabled:cursor-not-allowed disabled:opacity-50">
                    Continue to intent
                  </button>
                </div>
              ) : null}
            </div>
          ) : null}

          {createStep >= 3 ? (
            <div className="rounded-[24px] border border-white/[0.08] bg-canvas-deep p-4">
              <div className="mb-4 flex items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <span className="flex h-8 w-8 items-center justify-center rounded-full bg-teal/[0.12] text-cyan">3</span>
                  <div>
                    <h4 className="font-semibold text-white">Curation intent</h4>
                    <p className="text-xs text-zinc-500">{selectedGenreCount} genre signals selected for scoring and hook generation.</p>
                  </div>
                </div>
                <span className="rounded-full border border-cyan/[0.24] bg-teal/[0.08] px-3 py-1 text-xs font-semibold text-cyan">{selectedGenreCount}/{genreOptions.length}</span>
              </div>
              <div className="flex flex-wrap gap-2">
                {genreOptions.map((genre) => {
                  const active = config.genres.includes(genre.id);
                  return (
                    <button
                      key={genre.id}
                      type="button"
                      onClick={() => toggleGenre(genre.id)}
                      className={`inline-flex min-h-10 items-center gap-2 rounded-full border px-3 py-2 text-sm font-semibold transition ${active ? "border-cyan bg-teal/[0.16] text-white" : "border-white/[0.08] bg-black/24 text-zinc-400 hover:border-white/[0.16] hover:text-white"}`}
                      aria-pressed={active}
                      title={genre.description}
                    >
                      {active ? <BadgeCheck className="h-4 w-4 text-cyan" /> : null}
                      {genre.label}
                    </button>
                  );
                })}
              </div>
            </div>
          ) : null}

          {createStep >= 3 ? (
            <div className="rounded-[24px] border border-white/[0.08] bg-canvas-deep p-4">
              <div className="mb-4 flex items-center gap-3">
                <span className="flex h-8 w-8 items-center justify-center rounded-full bg-teal/[0.12] text-cyan">4</span>
                <div>
                  <h4 className="font-semibold text-white">Brand and engine</h4>
                  <p className="text-xs text-zinc-500">Brand system and low-level engine settings stay compact.</p>
                </div>
              </div>
              <div className="grid gap-2 text-sm font-medium text-zinc-300">
                <span>Brand template</span>
                <div className="grid gap-2 sm:grid-cols-2">
                  {(templates.length ? templates : [{id: "default", label: "Default Workspace Style", path: defaultTemplatePath}]).map((template) => {
                    const active = config.brandTemplate === template.path;
                    return (
                      <button
                        key={template.id}
                        type="button"
                        onClick={() => update({brandTemplate: template.path})}
                        className={`flex items-center justify-between rounded-xl border px-4 py-3 text-left transition ${
                          active
                            ? "border-cyan bg-cyan/[0.05] text-white shadow-[0_4px_12px_rgba(102,232,249,0.06)]"
                            : "border-white/[0.08] bg-black/24 text-zinc-400 hover:border-white/[0.16] hover:text-white"
                        }`}
                      >
                        <span className="text-xs font-semibold">{template.label}</span>
                        <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${active ? "bg-cyan text-ink" : "bg-white/[0.08] text-zinc-500"}`}>
                          {active ? "Active" : "Select"}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>
              <details className="mt-4 rounded-[20px] border border-white/[0.08] bg-black/20 p-3">
                <summary className="cursor-pointer list-none text-sm font-semibold text-zinc-200">
                  Advanced engine settings
                  <span className="ml-2 text-xs font-medium text-zinc-500">hyperframes · {config.captionSource} · {config.llmProvider}</span>
                </summary>
                <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <SelectTile label="Caption" value={config.captionSource} options={["whisper", "hybrid", "youtube"]} onChange={(value) => update({captionSource: value})} />
                  <SelectTile label="Speech language" value={config.speechLanguage} options={["id", "ar", "en", "ms"]} onChange={(value) => update({speechLanguage: value})} />
                  <SelectTile label="Transcript" value={config.transcriptLanguages} options={["id,en", "id", "en,id", "ar,id", "ms,id"]} onChange={(value) => update({transcriptLanguages: value})} />
                  <SelectTile label="LLM" value={config.llmProvider} options={["deepseek", "openai", "groq", "none"]} onChange={(value) => update({llmProvider: value})} />
                  <SelectTile label="Quality" value={config.quality} options={["production", "draft"]} onChange={(value) => update({quality: value})} />
                </div>
                {!hyperframesReady ? (
                  <p className="mt-3 text-xs leading-5 text-zinc-500">HyperFrames is the primary renderer. Runtime checks must pass before live generation starts.</p>
                ) : (
                  <p className="mt-3 text-xs leading-5 text-cyan">HyperFrames is ready. Legacy render fallback is reserved for old jobs only.</p>
                )}
              </details>
            </div>
          ) : null}

          {createStep >= 3 ? (
            <div className="grid gap-3">
              <SlideToConfirm
                label="Slide to generate batch"
                activeLabel="Starting batch..."
                onConfirm={onGenerate}
                isLoading={isStarting}
                disabled={!config.sourceUrl.trim()}
              />
              {renderActionStatus(actionState)}
            </div>
          ) : null}
        </div>
      </div>

      <div className="grid min-w-0 gap-5">
        <details className="min-w-0 rounded-[24px] border border-white/[0.08] bg-surface p-4 sm:rounded-[28px] sm:p-5">
          <summary className="mb-4 flex cursor-pointer list-none flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0">
              <h3 className="text-xl font-semibold text-white">Production monitor</h3>
              <p className="mt-1 text-sm leading-6 text-zinc-400">Open this only while a batch is running or when a run fails.</p>
            </div>
            <span className={`w-fit rounded-full border px-3 py-1 text-xs font-semibold ${statusTone(latest?.status || "empty")}`}>{latest?.status || "No job"}</span>
          </summary>
          {latest ? (
            <div className="grid gap-4">
              <div className="grid min-w-0 gap-2 rounded-[24px] border border-white/[0.08] bg-canvas-deep p-4">
                <div className="flex min-w-0 items-center justify-between gap-3 text-sm">
                  <span className="min-w-0 truncate font-semibold text-white">{latest.count} clips · {latest.llm_provider}/{latest.caption_source}</span>
                  <span className="font-semibold text-cyan">{latestProgress}%</span>
                </div>
                <div className="h-2.5 overflow-hidden rounded-full bg-surface-strong">
                  <div className="h-full rounded-full bg-cyan transition-all" style={{width: `${Math.max(4, latestProgress)}%`}} />
                </div>
              </div>
              <div className="grid gap-2 text-xs md:grid-cols-3">
                {renderReadinessLine({ready: latestProgress >= 20, label: "Curate", detail: "Moments"})}
                {renderReadinessLine({ready: latestProgress >= 55, label: "Captions", detail: "ASR"})}
                {renderReadinessLine({ready: latestProgress >= 90, label: "Render", detail: "Output"})}
              </div>
              <div className="min-w-0 rounded-[24px] border border-white/[0.08] bg-canvas-deep p-4">
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Runtime log</span>
                  <span className="text-xs text-zinc-600">Collapsed by default</span>
                </div>
                <pre className="max-h-52 overflow-auto whitespace-pre-wrap break-words rounded-2xl bg-black/40 p-3 text-[11px] leading-5 text-zinc-400">{latest.error || latest.log_text || "Waiting for logs..."}</pre>
              </div>
            </div>
          ) : (
            renderEmptyState("No active batch", "Start a generation run to see progress, logs, and output readiness here.")
          )}
        </details>

        <details className="min-w-0 rounded-[24px] border border-white/[0.08] bg-surface p-4 sm:rounded-[28px] sm:p-5">
          <summary className="flex cursor-pointer list-none flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
              <h3 className="text-lg font-semibold text-white">Run outside dashboard</h3>
              <p className="mt-1 text-sm text-zinc-500">Only open this when you need to run the same job outside the dashboard.</p>
            </div>
            <button type="button" onClick={(event) => { event.preventDefault(); onCopy(); }} className="inline-flex w-fit rounded-full bg-cyan px-4 py-2 text-sm font-semibold text-ink"><Copy className="mr-2 h-4 w-4" /> Copy</button>
          </summary>
          <pre className="mt-4 max-h-[360px] overflow-auto whitespace-pre-wrap break-words rounded-[24px] border border-white/[0.08] bg-canvas-deep p-4 text-xs leading-6 text-zinc-300 sm:p-5">{command}</pre>
        </details>
      </div>

      <FocusModal open={templatePickerOpen} title="Choose video template" subtitle="Pick the HyperFrames visual flow before generating clips." width="wide" onClose={() => setTemplatePickerOpen(false)}>
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
          {hyperframesTemplates.map((template) => {
            const active = config.hyperframesTemplate === template.id;
            return (
              <button
                key={template.id}
                type="button"
                onClick={() => {
                  update({
                    renderer: "hyperframes",
                    hyperframesTemplate: template.id,
                    brandSystemTemplateId: template.source === "brand_system" ? template.id : "",
                    brandTemplate: template.brand_template_path || config.brandTemplate,
                  });
                  setTemplatePickerOpen(false);
                }}
                className={`template-card min-w-0 rounded-[20px] border p-2.5 text-left transition sm:p-3 ${active ? "border-cyan/[0.45] bg-teal/[0.12] shadow-glow" : "border-white/[0.08] bg-canvas-deep hover:border-cyan/[0.22] hover:bg-teal/[0.05]"}`}
              >
                <TemplatePreview
                  template={template}
                  compact
                  gridCard
                  hideFooterLabel
                  frame={config.hyperframesFormat === "long_16_9" ? "long" : "short"}
                  hoverToPlay
                />
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-xs font-semibold uppercase tracking-wide text-cyan">{template.category}</p>
                    <h4 className="mt-1 truncate text-lg font-semibold text-white">{template.label}</h4>
                  </div>
                  {active ? <CheckCircle2 className="h-4 w-4 shrink-0 text-cyan" /> : null}
                </div>
                <p className="mt-2 line-clamp-2 text-sm leading-6 text-zinc-400">{template.best_for}</p>
              </button>
            );
          })}
        </div>
      </FocusModal>
    </section>
  );
}

function StepChip({step, label, active, done, enabled, onClick}: {step: number; label: string; active: boolean; done: boolean; enabled: boolean; onClick: () => void}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={!enabled}
      className={`flex h-11 items-center gap-3 rounded-full border px-4 text-sm font-semibold transition ${
        active ? "border-cyan bg-teal/[0.16] text-white" : done ? "border-teal/[0.24] bg-teal/[0.08] text-teal" : "border-white/[0.08] bg-black/20 text-zinc-400"
      } ${enabled ? "" : "cursor-not-allowed opacity-50"}`}
    >
      <span className={`grid h-6 w-6 place-items-center rounded-full text-xs font-bold ${active ? "bg-cyan text-ink" : done ? "bg-teal/[0.20] text-teal" : "bg-white/[0.10] text-zinc-300"}`}>
        {done ? "✓" : step}
      </span>
      {label}
    </button>
  );
}

function SelectTile({label, value, options, onChange}: {label: string; value: string; options: SelectTileOption[]; onChange: (value: string) => void}) {
  return (
    <label className="relative grid gap-1.5 rounded-[22px] border border-white/[0.08] bg-canvas-deep p-3 text-xs font-semibold uppercase tracking-wide text-zinc-500 transition-all focus-within:border-cyan/[0.30] hover:border-white/[0.14]">
      {label}
      <div className="relative flex items-center">
        <select
          value={value}
          onChange={(event) => onChange(event.target.value)}
          className="w-full appearance-none cursor-pointer bg-transparent text-sm font-semibold normal-case tracking-normal text-white outline-none pr-8"
        >
          {options.map((option) => {
            const item = typeof option === "string" ? {value: option, label: option, disabled: false} : option;
            return (
              <option key={item.value} value={item.value} disabled={item.disabled} className="bg-[#17171a] text-white">
                {item.label}
              </option>
            );
          })}
        </select>
        <span className="absolute right-1 pointer-events-none text-zinc-500">
          <ChevronDown className="h-4 w-4" />
        </span>
      </div>
    </label>
  );
}
