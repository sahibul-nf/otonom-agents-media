"use client";

import {Loader2, MoreHorizontal, Send} from "lucide-react";
import type {ReactNode} from "react";
import {platformLabel, type CredentialStatus, type PublishAttempt, type PublishTarget} from "@/lib/media-api";

type ActionUiState = {status: "running" | "done" | "failed"; message: string};

function SwitchControl({checked, disabled, label, onChange}: {checked: boolean; disabled?: boolean; label: string; onChange: () => void}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={onChange}
      className={`inline-flex h-8 items-center gap-2 rounded-full border px-2 text-xs font-semibold transition disabled:cursor-not-allowed disabled:opacity-50 ${
        checked ? "border-cyan/[0.45] bg-cyan text-ink" : "border-white/[0.12] bg-white/[0.04] text-zinc-400"
      }`}
    >
      <span>{label}</span>
      <span className={`relative h-5 w-9 rounded-full transition ${checked ? "bg-ink/25" : "bg-white/[0.10]"}`}>
        <span className={`absolute top-1 h-3 w-3 rounded-full bg-current transition ${checked ? "left-5 text-ink" : "left-1 text-zinc-500"}`} />
      </span>
    </button>
  );
}

function MenuAction({children, danger, onClick}: {children: ReactNode; danger?: boolean; onClick: () => void}) {
  return (
    <button
      type="button"
      onClick={(event) => {
        event.currentTarget.closest("details")?.removeAttribute("open");
        onClick();
      }}
      className={`flex h-10 w-full items-center rounded-xl px-3 text-left text-xs font-semibold transition ${
        danger ? "text-danger hover:bg-danger/[0.10]" : "text-zinc-200 hover:bg-white/[0.06] hover:text-cyan"
      }`}
    >
      {children}
    </button>
  );
}

function PlatformActionMenu({
  disabled,
  ready,
  supportsOauth,
  platform,
  onTestConnection,
  onStartOauth,
  onDisconnect,
}: {
  disabled?: boolean;
  ready: boolean;
  supportsOauth: boolean;
  platform: string;
  onTestConnection: (platform: string) => void;
  onStartOauth: (platform: string) => void;
  onDisconnect: (platform: string) => void;
}) {
  return (
    <details className="group relative">
      <summary
        aria-disabled={disabled}
        className={`grid h-10 w-10 list-none place-items-center rounded-full border border-white/[0.10] bg-white/[0.04] text-zinc-200 marker:hidden ${
          disabled ? "pointer-events-none opacity-50" : "cursor-pointer hover:border-cyan/[0.35] hover:text-cyan"
        }`}
      >
        <MoreHorizontal className="h-4 w-4" />
      </summary>
      <div className="absolute right-0 z-30 mt-2 w-52 overflow-hidden rounded-2xl border border-white/[0.10] bg-canvas-deep p-1 shadow-2xl">
        <MenuAction onClick={() => onTestConnection(platform)}>Test connection</MenuAction>
        <MenuAction onClick={() => (supportsOauth ? onStartOauth(platform) : onTestConnection(platform))}>{ready ? "Reconnect" : "Connect"}</MenuAction>
        <MenuAction danger onClick={() => onDisconnect(platform)}>Disconnect</MenuAction>
      </div>
    </details>
  );
}

function ChannelReadiness({
  ready,
  targeted,
  renderReadinessLine,
}: {
  ready: boolean;
  targeted: boolean;
  renderReadinessLine: (ready: boolean, label: string, detail: string) => ReactNode;
}) {
  return (
    <div className="mt-3 grid gap-1.5 rounded-2xl border border-white/[0.08] bg-black/15 p-3">
      {renderReadinessLine(ready, "Account", ready ? "Connected" : "Connect")}
      {renderReadinessLine(targeted, "Default target", targeted ? "On" : "Off")}
      {renderReadinessLine(true, "Publish controls", "Schedule")}
    </div>
  );
}

export function PublishSection({
  targets,
  credentials,
  attempts,
  selectedPlatforms,
  actionStates,
  oauthPlatforms,
  onTogglePlatform,
  onTestConnection,
  onStartOauth,
  onDisconnect,
  publicAccountLabel,
  publishActionHint,
  formatPlatformMode,
  cleanPublishStatus,
  statusTone,
  renderSettingTile,
  renderReadinessLine,
  renderEmptyState,
}: {
  targets: PublishTarget[];
  credentials: CredentialStatus | null;
  attempts: PublishAttempt[];
  selectedPlatforms: string[];
  actionStates: Record<string, ActionUiState>;
  oauthPlatforms: Set<string>;
  onTogglePlatform: (platform: string) => void;
  onTestConnection: (platform: string) => void;
  onStartOauth: (platform: string) => void;
  onDisconnect: (platform: string) => void;
  publicAccountLabel: (target: PublishTarget) => string;
  publishActionHint: (error?: string) => string;
  formatPlatformMode: (mode?: string) => string;
  cleanPublishStatus: (status?: string) => string;
  statusTone: (status: string) => string;
  renderSettingTile: (label: string, value: string | number) => ReactNode;
  renderReadinessLine: (ready: boolean, label: string, detail: string) => ReactNode;
  renderEmptyState: (title: string, text: string) => ReactNode;
}) {
  const latestByPlatform = new Map<string, PublishAttempt>();
  for (const attempt of attempts) {
    if (!latestByPlatform.has(attempt.platform)) latestByPlatform.set(attempt.platform, attempt);
  }

  return (
    <section className="grid gap-5 xl:grid-cols-[1fr_420px]">
      <div className="rounded-[28px] border border-white/[0.08] bg-surface p-5">
        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div>
            <h3 className="text-xl font-semibold text-white">Channels</h3>
            <p className="mt-1 text-sm text-zinc-400">Connect social accounts and choose default publish targets. Actual publishing happens from Schedule or clip actions.</p>
          </div>
          <div className="rounded-full border border-cyan/[0.25] bg-teal/[0.10] px-4 py-2 text-xs font-semibold text-cyan">
            {targets.filter((target) => credentials?.platforms[target.platform]?.ready).length}/{targets.length} connected
          </div>
        </div>
        <div className="mt-5 grid gap-3 md:grid-cols-2">
          {targets.map((target) => {
            const ready = credentials?.platforms[target.platform]?.ready;
            const credential = credentials?.platforms[target.platform];
            const selectedForPublish = selectedPlatforms.includes(target.platform);
            const latest = latestByPlatform.get(target.platform);
            const recovery = publishActionHint(latest?.error);
            const supportsOauth = oauthPlatforms.has(target.platform);
            const activeAction = [
              actionStates[`test:${target.platform}`],
              actionStates[`connect:${target.platform}`],
              actionStates[`disconnect:${target.platform}`],
              actionStates[`target:${target.platform}`],
            ].find((item) => item?.status === "running");
            const isBusy = Boolean(activeAction);
            return (
              <div key={target.platform} className={`rounded-[24px] border p-4 transition ${selectedForPublish ? "border-cyan/[0.30] bg-teal/[0.08]" : "border-white/[0.08] bg-canvas-deep"}`}>
                <div className="flex items-center justify-between">
                  <div className="grid h-11 w-11 place-items-center rounded-2xl bg-cyan text-ink"><Send className="h-5 w-5" /></div>
                  <SwitchControl checked={selectedForPublish} disabled={isBusy} label="Target" onChange={() => onTogglePlatform(target.platform)} />
                </div>
                <h4 className="mt-4 font-semibold text-white">{platformLabel(target.platform)}</h4>
                <p className="mt-1 text-sm text-zinc-400">{publicAccountLabel(target)}</p>
                <div className="mt-4 grid grid-cols-2 gap-2 text-xs text-zinc-400">
                  {renderSettingTile("Connection", ready ? "Connected" : "Needs setup")}
                  {renderSettingTile("Mode", formatPlatformMode(target.mode))}
                </div>
                <ChannelReadiness ready={Boolean(ready)} targeted={selectedForPublish} renderReadinessLine={renderReadinessLine} />
                {!ready ? (
                  <div className="mt-3 rounded-2xl border border-warning/20 bg-warning/[0.08] p-3 text-xs leading-5 text-warning">
                    Missing: {(credential?.missing_keys || []).join(", ") || "credential"}. Connect via OAuth/token setup before live publishing.
                  </div>
                ) : null}
                <div className="mt-4 rounded-2xl border border-white/[0.08] bg-black/20 p-3">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs uppercase tracking-wide text-zinc-500">Current attempt</span>
                    <span className={`inline-flex max-w-[70%] items-center gap-1 truncate rounded-full border px-2 py-1 text-xs font-semibold ${statusTone(activeAction ? "running" : latest?.status || "pending")}`}>
                      {activeAction ? <Loader2 className="h-3 w-3 shrink-0 animate-spin" /> : null}
                      <span className="truncate">{activeAction?.message || cleanPublishStatus(latest?.status)}</span>
                    </span>
                  </div>
                  {recovery ? <p className="mt-2 line-clamp-2 text-xs leading-5 text-danger">{recovery}</p> : null}
                  {activeAction ? <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/[0.08]"><div className="h-full w-2/3 animate-pulse rounded-full bg-cyan" /></div> : null}
                </div>
                <div className="mt-4 flex items-center gap-2">
                  <button
                    disabled={isBusy}
                    onClick={() => onTestConnection(target.platform)}
                    className="h-10 flex-1 rounded-full border border-cyan/[0.24] bg-teal/[0.08] text-xs font-semibold text-cyan disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    {actionStates[`test:${target.platform}`]?.status === "running" ? "Testing..." : "Test connection"}
                  </button>
                  <PlatformActionMenu
                    disabled={isBusy}
                    ready={Boolean(ready)}
                    supportsOauth={supportsOauth}
                    platform={target.platform}
                    onTestConnection={onTestConnection}
                    onStartOauth={onStartOauth}
                    onDisconnect={onDisconnect}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>
      <div className="rounded-[28px] border border-white/[0.08] bg-surface p-5">
        <h3 className="text-xl font-semibold text-white">Channel readiness</h3>
        <p className="mt-2 text-sm leading-6 text-zinc-400">Use this page to connect accounts. Schedule and publish controls live next to clips, where the content context is visible.</p>
        <div className="mt-5 grid gap-3">
          <div className="rounded-[22px] border border-cyan/[0.18] bg-teal/[0.08] p-4 text-sm leading-6 text-zinc-300">
            Scheduled items publish through the PM2 worker. For a one-off publish, open Schedule and run the due queue for the selected scheduled clip.
          </div>
          <div className="rounded-[22px] border border-white/[0.08] bg-canvas-deep p-4">
            <p className="text-xs uppercase tracking-wide text-zinc-500">Default targets</p>
            <div className="mt-3 grid gap-2">
              {targets.map((target) => {
                const ready = credentials?.platforms[target.platform]?.ready;
                const enabled = selectedPlatforms.includes(target.platform);
                return (
                  <div key={target.platform}>
                    {renderReadinessLine(Boolean(ready && enabled), platformLabel(target.platform), !enabled ? "Target off" : ready ? "Ready" : "Reconnect")}
                  </div>
                );
              })}
            </div>
          </div>
          {Array.from(latestByPlatform.values()).length ? Array.from(latestByPlatform.values()).map((attempt) => (
            <div key={attempt.id} className="rounded-[18px] border border-white/[0.08] bg-canvas-deep p-3">
              <div className="flex items-center justify-between gap-2">
                <p className="text-sm font-semibold text-white">{platformLabel(attempt.platform)}</p>
                <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${statusTone(attempt.status)}`}>{cleanPublishStatus(attempt.status)}</span>
              </div>
              {attempt.error ? <p className="mt-2 text-xs leading-5 text-danger">{publishActionHint(attempt.error)}</p> : null}
            </div>
          )) : renderEmptyState("No channel activity yet", "Connection tests and scheduled publishing attempts will appear here.")}
        </div>
      </div>
    </section>
  );
}
