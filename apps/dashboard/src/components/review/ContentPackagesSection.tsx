"use client";

import {Check, Package, Send} from "lucide-react";

export type ContentPackageRow = {
  id: string;
  profile_id?: string;
  format: string;
  job: string;
  status: string;
  caption: string;
  title?: string;
  video_engine?: string | null;
  brand_preset?: string;
  qa?: {passed?: boolean; errors?: string[]};
  source?: {kind?: string; ref?: string};
  meta?: {
    batch_id?: string;
    batch_formats?: string[];
    explainer_job_id?: string;
    explainer_status?: string;
    explainer_error?: string;
    explainer_duration_seconds?: number;
  };
};

type ActionUiState = {status: "running" | "done" | "failed"; message: string};

export type ContentPackagesSectionProps = {
  packages: ContentPackageRow[];
  actionStates: Record<string, ActionUiState>;
  onApprove: (packageId: string) => void;
  onPublish?: (packageId: string) => void;
  onOpenExplainer?: (jobId: string) => void;
};

function explainerStatusLabel(status: string | undefined): string | null {
  if (!status) return null;
  if (status === "planned") return "Explainer queued";
  if (status === "rendering") return "Explainer rendering…";
  if (status === "rendered") return "Video ready";
  if (status === "failed") return "Explainer failed";
  return `Explainer: ${status}`;
}

export function ContentPackagesSection({
  packages,
  actionStates,
  onApprove,
  onPublish,
  onOpenExplainer,
}: ContentPackagesSectionProps) {
  if (!packages.length) {
    return null;
  }

  return (
    <section className="mb-8 rounded-2xl border border-white/10 bg-zinc-900/40 p-5">
      <div className="mb-4 flex items-center gap-2 text-sm font-medium text-zinc-200">
        <Package className="h-4 w-4 text-cyan-400" aria-hidden />
        Content packages
        <span className="text-zinc-500">({packages.length})</span>
      </div>
      <p className="mb-4 text-xs text-zinc-500">
        Text, stills, carousels, shorts, long-form, and clips — separate from video clip candidates below.
      </p>
      <ul className="space-y-3">
        {packages.map((pkg) => {
          const approveKey = `package:approve:${pkg.id}`;
          const publishKey = `package:publish:${pkg.id}`;
          const busy = actionStates[approveKey]?.status === "running";
          const publishBusy = actionStates[publishKey]?.status === "running";
          const canApprove = pkg.status === "ready_for_review" || (pkg.status === "draft" && pkg.qa?.passed);
          const videoReady =
            pkg.meta?.explainer_status === "rendered" ||
            (pkg.format !== "short" && pkg.format !== "long_form");
          const canPublishVideo =
            pkg.status === "approved" &&
            (pkg.format === "short" || pkg.format === "long_form" || pkg.format === "clip") &&
            videoReady &&
            onPublish;
          const canPublishImage =
            pkg.status === "approved" && (pkg.format === "still" || pkg.format === "carousel") && pkg.qa?.passed && onPublish;
          const canPublish =
            (pkg.status === "approved" && pkg.format === "text_only" && onPublish) ||
            canPublishVideo ||
            canPublishImage;
          const publishLabel =
            pkg.format === "text_only"
              ? "Publish (Telegram)"
              : pkg.format === "still" || pkg.format === "carousel"
                ? "Publish images (Instagram)"
                : "Publish video (Telegram)";
          const explainerLabel = explainerStatusLabel(pkg.meta?.explainer_status);
          return (
            <li
              key={pkg.id}
              className="rounded-xl border border-white/5 bg-zinc-950/50 p-4"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2 text-xs text-zinc-400">
                    <span className="rounded bg-cyan-500/15 px-2 py-0.5 font-mono text-cyan-300">{pkg.format}</span>
                    <span>{pkg.job}</span>
                    <span className="text-zinc-600">·</span>
                    <span>{pkg.status}</span>
                    {pkg.video_engine ? <span className="text-zinc-500">engine {pkg.video_engine}</span> : null}
                    {pkg.brand_preset ? <span className="text-zinc-500">preset {pkg.brand_preset}</span> : null}
                    {pkg.meta?.batch_id ? (
                      <span className="rounded bg-violet-500/15 px-2 py-0.5 font-mono text-violet-200">
                        batch {pkg.meta.batch_id}
                      </span>
                    ) : null}
                    {explainerLabel ? (
                      <span
                        className={
                          pkg.meta?.explainer_status === "failed"
                            ? "rounded bg-red-500/15 px-2 py-0.5 text-red-300"
                            : pkg.meta?.explainer_status === "rendered"
                              ? "rounded bg-emerald-500/15 px-2 py-0.5 text-emerald-300"
                              : "rounded bg-amber-500/15 px-2 py-0.5 text-amber-200"
                        }
                      >
                        {explainerLabel}
                      </span>
                    ) : null}
                  </div>
                  {pkg.meta?.explainer_job_id ? (
                    <p className="mt-1 font-mono text-xs text-zinc-500">
                      explainer job {pkg.meta.explainer_job_id}
                      {onOpenExplainer ? (
                        <button
                          type="button"
                          className="ml-2 text-cyan-400 hover:text-cyan-300"
                          onClick={() => onOpenExplainer(pkg.meta!.explainer_job_id!)}
                        >
                          Open in Explainer
                        </button>
                      ) : null}
                    </p>
                  ) : null}
                  {pkg.title ? <p className="mt-2 font-medium text-zinc-100">{pkg.title}</p> : null}
                  <p className="mt-2 line-clamp-4 whitespace-pre-wrap text-sm text-zinc-300">{pkg.caption}</p>
                  {pkg.qa?.errors?.length ? (
                    <p className="mt-2 text-xs text-amber-400/90">QA: {pkg.qa.errors.join("; ")}</p>
                  ) : null}
                  {pkg.source?.ref ? (
                    <p className="mt-2 truncate text-xs text-zinc-600">{pkg.source.kind}: {pkg.source.ref}</p>
                  ) : null}
                </div>
                <div className="flex flex-col gap-2">
                  {canApprove ? (
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => onApprove(pkg.id)}
                      className="inline-flex items-center gap-1.5 rounded-lg bg-cyan-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-cyan-500 disabled:opacity-50"
                    >
                      <Check className="h-3.5 w-3.5" aria-hidden />
                      Approve
                    </button>
                  ) : null}
                  {canPublish ? (
                    <button
                      type="button"
                      disabled={publishBusy}
                      onClick={() => onPublish(pkg.id)}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-violet-500/40 bg-violet-500/10 px-3 py-1.5 text-xs font-medium text-violet-200 hover:bg-violet-500/20 disabled:opacity-50"
                    >
                      <Send className="h-3.5 w-3.5" aria-hidden />
                      {publishLabel}
                    </button>
                  ) : null}
                </div>
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
