"use client";

import {Brain, Check, Loader2, Plug, Zap} from "lucide-react";
import {type FormEvent, useState} from "react";
import type {CredentialStatus} from "@/lib/media-api";

type ActionUiState = {status: "running" | "done" | "failed"; message: string};

export type LlmConnectorRow = {
  id: string;
  label: string;
  binary?: string;
  detected?: boolean;
  version?: string;
  state: string;
  active?: boolean;
  connected?: boolean;
  auth_hint?: string;
  command_preview?: string;
  last_error?: string;
  command_outdated?: boolean;
};

export type LlmStatusPayload = {
  profile_id?: string;
  providers?: Record<string, {ready?: boolean}>;
  agent?: {ready?: boolean; connector_id?: string; state?: string; command_set?: boolean};
  connectors?: LlmConnectorRow[];
};

const LLM_FIELDS = [
  {id: "OPENAI_API_KEY", label: "OpenAI API key", provider: "openai"},
  {id: "DEEPSEEK_API_KEY", label: "DeepSeek API key", provider: "deepseek"},
  {id: "GROQ_API_KEY", label: "Groq API key", provider: "groq"},
  {id: "OTONOM_LLM_AGENT_COMMAND", label: "Custom agent CLI command", provider: "agent"},
] as const;

function stateLabel(state: string): string {
  if (state === "ready") return "Ready";
  if (state === "configured") return "Connected";
  if (state === "stale") return "Reconnect";
  if (state === "error") return "Error";
  if (state === "detected") return "Detected";
  if (state === "undetected") return "Not installed";
  return state;
}

function stateClass(state: string): string {
  if (state === "ready") return "bg-emerald-500/15 text-emerald-300";
  if (state === "configured") return "bg-cyan-500/15 text-cyan-200";
  if (state === "stale") return "bg-amber-500/20 text-amber-200";
  if (state === "error") return "bg-red-500/15 text-red-300";
  if (state === "detected") return "bg-amber-500/15 text-amber-200";
  return "bg-zinc-800 text-zinc-500";
}

function agentPillLabel(agent?: LlmStatusPayload["agent"], fallbackReady?: boolean): string {
  const state = agent?.state;
  if (state === "ready") return "ready";
  if (state === "configured") return "connected (test pending)";
  if (agent?.command_set || fallbackReady) return "connected (test pending)";
  return "not set";
}

function agentPillReady(agent?: LlmStatusPayload["agent"], fallbackReady?: boolean): boolean {
  if (agent?.state === "ready") return true;
  if (agent?.state === "configured") return false;
  return Boolean(fallbackReady);
}

export type LlmKeysSectionProps = {
  credentials: CredentialStatus | null;
  profileId: string;
  llmStatus: LlmStatusPayload | null;
  llmStatusLoading?: boolean;
  actionStates: Record<string, ActionUiState>;
  onSaveLlm: (values: Record<string, string>) => Promise<void>;
  onConnectConnector?: (connectorId: string, action?: "connect" | "activate" | "deactivate") => Promise<void>;
  onTestAgent?: () => Promise<void>;
};

export function LlmKeysSection({
  credentials,
  profileId,
  llmStatus,
  llmStatusLoading,
  actionStates,
  onSaveLlm,
  onConnectConnector,
  onTestAgent,
}: LlmKeysSectionProps) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const busy = actionStates[`llm:save:${profileId}`]?.status === "running";
  const llm = credentials?.llm;
  const agentSummary = llmStatus?.agent ?? (llm?.agent as LlmStatusPayload["agent"] | undefined);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    const values = Object.fromEntries(Object.entries(draft).filter(([, v]) => v.trim()));
    if (!Object.keys(values).length) return;
    await onSaveLlm(values);
    setDraft({});
    setOpen(false);
  }

  const connectors = llmStatus?.connectors?.filter((c) => c.id !== "custom") ?? [];
  const showTest =
    onTestAgent &&
    Boolean(agentSummary?.connector_id) &&
    agentSummary?.state !== "undetected" &&
    (agentSummary?.command_set || agentSummary?.ready);

  return (
    <section className="mt-8 rounded-2xl border border-white/[0.08] bg-black/20 p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-sm font-medium text-zinc-200">
          <Brain className="h-4 w-4 text-violet-400" aria-hidden />
          LLM connectors
          {llmStatusLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin text-zinc-500" aria-hidden /> : null}
        </div>
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="rounded-lg border border-white/[0.10] px-3 py-1.5 text-xs font-semibold text-zinc-300 hover:border-violet-400/40"
        >
          {open ? "Close" : "API keys / custom CLI"}
        </button>
      </div>
      <p className="mt-2 text-xs text-zinc-500">
        Connect multiple harnesses (e.g. Cursor and Antigravity together). Every row marked{" "}
        <span className="text-violet-300">Active</span> runs for{" "}
        <code className="text-zinc-400">llm_provider=agent</code> — first success wins if one fails. Same idea as OpenMausBot and{" "}
        <a href="https://t3.codes" className="text-cyan-400 hover:underline" target="_blank" rel="noreferrer">
          T3 Code
        </a>
        . No API keys resold.
      </p>

      <ul className="mt-3 flex flex-wrap gap-2 text-xs">
        {LLM_FIELDS.map((field) => {
          const ready =
            field.provider === "agent"
              ? agentPillReady(agentSummary, llm?.agent?.ready)
              : llm?.[field.provider]?.ready;
          const label =
            field.provider === "agent"
              ? agentPillLabel(agentSummary, llm?.agent?.ready)
              : ready
                ? "ready"
                : "not set";
          return (
            <li
              key={field.id}
              className={`rounded-full px-2.5 py-1 ${ready ? "bg-emerald-500/15 text-emerald-300" : "bg-zinc-800 text-zinc-500"}`}
            >
              {field.provider} {label}
            </li>
          );
        })}
      </ul>

      <div className="mt-4 space-y-2">
        {connectors.length === 0 && !llmStatusLoading ? (
          <p className="text-xs text-zinc-600">Harness list unavailable — check media-engine is running.</p>
        ) : null}
        {connectors.map((row) => {
          const connectKey = `llm:connect:${row.id}`;
          const connectBusy = actionStates[connectKey]?.status === "running";
          const canConnect = row.detected && row.id !== "custom" && onConnectConnector;
          const needsReconnect = row.state === "stale" || row.command_outdated;
          const connectLabel = needsReconnect ? "Reconnect" : row.connected && !row.active ? "Enable" : "Connect";
          const connectAction: "connect" | "activate" | "deactivate" =
            row.connected && !row.active && !needsReconnect ? "activate" : "connect";
          const showConnectButton = canConnect && (!row.connected || needsReconnect || !row.active);
          return (
            <div
              key={row.id}
              className="rounded-xl border border-white/[0.06] bg-zinc-950/40 px-3 py-3"
            >
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-medium text-zinc-100">{row.label}</span>
                    <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase ${stateClass(row.state)}`}>
                      {stateLabel(row.state)}
                    </span>
                    {row.active ? (
                      <span className="text-[10px] uppercase tracking-wider text-violet-300">Active</span>
                    ) : row.connected ? (
                      <span className="text-[10px] uppercase tracking-wider text-zinc-500">Connected</span>
                    ) : null}
                  </div>
                  <p className="mt-1 text-[11px] text-zinc-500">{row.auth_hint}</p>
                  {row.version ? <p className="mt-0.5 font-mono text-[10px] text-zinc-600">{row.version}</p> : null}
                  {row.last_error ? <p className="mt-1 text-[11px] text-red-300/90">{row.last_error}</p> : null}
                </div>
                <div className="flex shrink-0 gap-2">
                  {showConnectButton ? (
                    <button
                      type="button"
                      disabled={connectBusy}
                      onClick={() => void onConnectConnector(row.id, connectAction)}
                      className={`inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-[11px] font-semibold disabled:opacity-50 ${
                        connectAction === "activate"
                          ? "border border-violet-400/40 bg-violet-500/15 text-violet-100 hover:bg-violet-500/25"
                          : "bg-violet-600 text-white hover:bg-violet-500"
                      }`}
                    >
                      {connectBusy ? <Loader2 className="h-3 w-3 animate-spin" /> : <Plug className="h-3 w-3" />}
                      {connectLabel}
                    </button>
                  ) : null}
                  {row.active && row.connected && onConnectConnector ? (
                    <button
                      type="button"
                      disabled={connectBusy}
                      onClick={() => void onConnectConnector(row.id, "deactivate")}
                      className="inline-flex items-center gap-1 rounded-lg border border-white/[0.10] px-2.5 py-1.5 text-[11px] font-semibold text-zinc-400 hover:border-zinc-500 hover:text-zinc-200 disabled:opacity-50"
                    >
                      Pause
                    </button>
                  ) : null}
                  {row.active && row.connected && !showConnectButton ? (
                    <span className="inline-flex items-center gap-1 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-1.5 text-[11px] font-semibold text-emerald-200">
                      <Check className="h-3 w-3" /> Active
                    </span>
                  ) : null}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {showTest ? (
        <button
          type="button"
          disabled={
            actionStates[`llm:test:${profileId}`]?.status === "running" ||
            agentSummary?.state === "stale"
          }
          onClick={() => void onTestAgent?.()}
          className="mt-3 inline-flex items-center gap-1.5 rounded-lg border border-white/[0.10] px-3 py-2 text-xs font-semibold text-zinc-200 hover:border-cyan/40 disabled:opacity-50"
        >
          {actionStates[`llm:test:${profileId}`]?.status === "running" ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Zap className="h-3.5 w-3.5 text-amber-300" />
          )}
          Test active harness (JSON ping)
        </button>
      ) : null}
      {agentSummary?.state === "stale" ? (
        <p className="mt-2 text-[11px] text-amber-200/90">Reconnect the active harness before running Test.</p>
      ) : null}

      {open ? (
        <form onSubmit={(e) => void onSubmit(e)} className="mt-4 space-y-3 border-t border-white/[0.06] pt-4">
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
