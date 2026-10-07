"use client";

import {Brain, Loader2} from "lucide-react";
import {type FormEvent, useState} from "react";
import type {CredentialStatus} from "@/lib/media-api";

type ActionUiState = {status: "running" | "done" | "failed"; message: string};

const LLM_FIELDS = [
  {id: "OPENAI_API_KEY", label: "OpenAI API key", provider: "openai"},
  {id: "DEEPSEEK_API_KEY", label: "DeepSeek API key", provider: "deepseek"},
  {id: "GROQ_API_KEY", label: "Groq API key", provider: "groq"},
  {id: "OTONOM_LLM_AGENT_COMMAND", label: "Local agent CLI command", provider: "agent"},
] as const;

export type LlmKeysSectionProps = {
  credentials: CredentialStatus | null;
  profileId: string;
  actionStates: Record<string, ActionUiState>;
  onSaveLlm: (values: Record<string, string>) => Promise<void>;
};

export function LlmKeysSection({credentials, profileId, actionStates, onSaveLlm}: LlmKeysSectionProps) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const busy = actionStates[`llm:save:${profileId}`]?.status === "running";
  const llm = credentials?.llm;

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    const values = Object.fromEntries(Object.entries(draft).filter(([, v]) => v.trim()));
    if (!Object.keys(values).length) return;
    await onSaveLlm(values);
    setDraft({});
    setOpen(false);
  }

  return (
    <section className="mt-8 rounded-2xl border border-white/[0.08] bg-black/20 p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-sm font-medium text-zinc-200">
          <Brain className="h-4 w-4 text-violet-400" aria-hidden />
          LLM keys
        </div>
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="rounded-lg border border-white/[0.10] px-3 py-1.5 text-xs font-semibold text-zinc-300 hover:border-violet-400/40"
        >
          {open ? "Close" : "Paste API key or agent CLI"}
        </button>
      </div>
      <p className="mt-2 text-xs text-zinc-500">
        Same pattern as OpenMausBot: store provider keys in the workspace vault, or set a local agent command that prints JSON on stdout.
      </p>
      <ul className="mt-3 flex flex-wrap gap-2 text-xs">
        {LLM_FIELDS.map((field) => {
          const ready = llm?.[field.provider]?.ready;
          return (
            <li
              key={field.id}
              className={`rounded-full px-2.5 py-1 ${ready ? "bg-emerald-500/15 text-emerald-300" : "bg-zinc-800 text-zinc-500"}`}
            >
              {field.provider} {ready ? "ready" : "not set"}
            </li>
          );
        })}
      </ul>
      {open ? (
        <form onSubmit={(e) => void onSubmit(e)} className="mt-4 space-y-3">
          {LLM_FIELDS.map((field) => (
            <label key={field.id} className="block text-xs text-zinc-400">
              {field.label}
              <input
                type={field.id.includes("KEY") ? "password" : "text"}
                autoComplete="off"
                className="mt-1 w-full rounded-lg border border-white/[0.08] bg-zinc-950 px-3 py-2 text-sm text-zinc-100"
                placeholder={field.id}
                value={draft[field.id] || ""}
                onChange={(e) => setDraft((d) => ({...d, [field.id]: e.target.value}))}
              />
            </label>
          ))}
          <button
            type="submit"
            disabled={busy}
            className="inline-flex items-center gap-2 rounded-lg bg-violet-600 px-4 py-2 text-xs font-semibold text-white hover:bg-violet-500 disabled:opacity-50"
          >
            {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
            Save LLM settings
          </button>
        </form>
      ) : null}
    </section>
  );
}
