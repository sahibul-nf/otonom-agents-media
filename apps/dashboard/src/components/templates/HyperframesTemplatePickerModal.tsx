"use client";

import {CheckCircle2} from "lucide-react";
import {FocusModal} from "@/components/FocusModal";
import {TemplatePreview} from "@/components/templates/TemplatePreview";
import {friendlyTemplateStatus} from "@/components/templates/template-ui";
import type {HyperframesTemplate} from "@/lib/media-api";

export function HyperframesTemplatePickerModal({
  open,
  title,
  subtitle,
  templates,
  selectedId,
  frame = "short",
  onClose,
  onSelect,
}: {
  open: boolean;
  title: string;
  subtitle: string;
  templates: HyperframesTemplate[];
  selectedId?: string;
  frame?: "short" | "long";
  onClose: () => void;
  onSelect: (template: HyperframesTemplate) => void;
}) {
  return (
    <FocusModal open={open} title={title} subtitle={subtitle} width="wide" onClose={onClose}>
      {templates.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-white/[0.10] px-4 py-10 text-center text-sm text-zinc-500">
          No templates in this list yet.
        </p>
      ) : (
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
          {templates.map((template) => {
            const active = selectedId === template.id;
            return (
              <div
                key={template.id}
                className={`template-card min-w-0 rounded-[20px] border text-left transition sm:p-3 ${active ? "border-cyan/[0.45] bg-teal/[0.12] shadow-glow" : "border-white/[0.08] bg-canvas-deep hover:border-cyan/[0.22] hover:bg-teal/[0.05]"} p-2.5`}
              >
                <TemplatePreview template={template} compact gridCard hideFooterLabel frame={frame} hoverToPlay />
                <button
                  type="button"
                  onClick={() => onSelect(template)}
                  className="mt-2 block w-full text-left"
                  aria-pressed={active}
                  aria-label={`Use ${template.label}`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="text-xs font-semibold uppercase tracking-wide text-cyan">{template.category}</p>
                        <span className="rounded-full border border-white/[0.10] bg-black/30 px-2 py-0.5 text-[10px] font-semibold text-zinc-400">
                          {friendlyTemplateStatus(template.status)}
                        </span>
                      </div>
                      <h4 className="mt-1 truncate text-lg font-semibold text-white">{template.label}</h4>
                    </div>
                    {active ? <CheckCircle2 className="h-4 w-4 shrink-0 text-cyan" /> : null}
                  </div>
                  <p className="mt-2 line-clamp-2 text-sm leading-6 text-zinc-400">{template.best_for}</p>
                </button>
              </div>
            );
          })}
        </div>
      )}
    </FocusModal>
  );
}
