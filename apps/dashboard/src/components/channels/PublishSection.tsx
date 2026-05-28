"use client";

import {Loader2, MoreHorizontal, Send, ShieldCheck, CheckCircle2, AlertCircle, RefreshCcw, Wifi, ExternalLink, Sparkles, Youtube, Instagram, Facebook, Linkedin, HelpCircle} from "lucide-react";
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
      className={`inline-flex h-8 items-center gap-2.5 rounded-full border px-3 text-xs font-semibold transition-all duration-300 disabled:cursor-not-allowed disabled:opacity-50 ${
        checked 
          ? "border-cyan/[0.45] bg-cyan text-ink shadow-[0_4px_12px_rgba(102,232,249,0.15)]" 
          : "border-white/[0.08] bg-black/24 text-zinc-400 hover:border-white/[0.14]"
      }`}
    >
      <span>{label}</span>
      <span className={`relative h-4 w-7 rounded-full transition-colors ${checked ? "bg-ink/20" : "bg-white/[0.10]"}`}>
        <span className={`absolute top-0.5 h-3 w-3 rounded-full bg-current transition-all ${checked ? "left-3.5 text-ink" : "left-0.5 text-zinc-500"}`} />
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
      className={`flex h-10 w-full items-center rounded-xl px-3 text-left text-xs font-bold uppercase tracking-wider transition-colors duration-150 ${
        danger ? "text-danger hover:bg-danger/[0.10]" : "text-zinc-300 hover:bg-white/[0.05] hover:text-cyan"
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
        className={`grid h-10 w-10 list-none place-items-center rounded-full border border-white/[0.08] bg-black/20 text-zinc-400 marker:hidden ${
          disabled ? "pointer-events-none opacity-50" : "cursor-pointer hover:border-cyan/[0.30] hover:text-cyan hover:bg-black/40 transition-colors"
        }`}
      >
        <MoreHorizontal className="h-4 w-4" />
      </summary>
      <div className="absolute right-0 z-30 mt-2 w-52 overflow-hidden rounded-2xl border border-white/[0.08] bg-surface-panel p-1 shadow-2xl backdrop-blur-xl">
        <MenuAction onClick={() => onTestConnection(platform)}>Test Connection</MenuAction>
        <MenuAction onClick={() => (supportsOauth ? onStartOauth(platform) : onTestConnection(platform))}>{ready ? "Reconnect Account" : "Connect Account"}</MenuAction>
        <MenuAction danger onClick={() => onDisconnect(platform)}>Disconnect</MenuAction>
      </div>
    </details>
  );
}

function getPlatformIcon(platform: string) {
  switch (platform) {
    case "youtube":
      return <Youtube className="h-5 w-5" />;
    case "instagram":
      return <Instagram className="h-5 w-5" />;
    case "facebook":
      return <Facebook className="h-5 w-5" />;
    case "linkedin":
      return <Linkedin className="h-5 w-5" />;
    case "tiktok":
      return (
        <svg className="h-5 w-5 fill-current" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
          <path d="M12.53.02C13.84 0 15.14.01 16.44 0c.08 1.53.63 3.09 1.75 4.17 1.12 1.11 2.7 1.62 4.24 1.79v4.03c-1.44-.05-2.89-.54-3.99-1.52-.28-.25-.53-.53-.76-.83v6.24c0 1.62-.35 3.26-1.19 4.6-1.12 1.83-3.13 3.12-5.32 3.38-2.23.27-4.63-.33-6.26-1.92C3.34 18.23 2.5 15.65 2.87 13.1c.33-2.3 1.73-4.48 3.86-5.46 1.4-.64 2.98-.82 4.49-.55v4.17c-1.13-.3-2.38-.11-3.32.55-1 .71-1.55 1.99-1.48 3.23.05 1.08.64 2.1 1.53 2.65.9.56 2.06.63 3.01.2 1.03-.47 1.73-1.54 1.73-2.67V.02h-.16z"/>
        </svg>
      );
    default:
      return <HelpCircle className="h-5 w-5" />;
  }
}

// Custom brand-specific themes for social platforms
const platformThemes: Record<string, {glow: string; text: string; bg: string; iconBg: string}> = {
  youtube: {
    glow: "rgba(239,68,68,0.15)",
    text: "text-red-500",
    bg: "bg-red-500/5 hover:bg-red-500/10",
    iconBg: "bg-red-600/10 text-red-500 border border-red-500/20",
  },
  tiktok: {
    glow: "rgba(98,238,248,0.15)",
    text: "text-cyan",
    bg: "bg-cyan/5 hover:bg-cyan/10",
    iconBg: "bg-black text-cyan border border-cyan/20 shadow-[0_0_12px_rgba(98,238,248,0.15)]",
  },
  instagram: {
    glow: "rgba(236,72,153,0.15)",
    text: "text-pink-500",
    bg: "bg-pink-500/5 hover:bg-pink-500/10",
    iconBg: "bg-gradient-to-tr from-yellow-500/10 via-pink-500/10 to-purple-500/10 text-pink-500 border border-pink-500/20",
  },
  facebook: {
    glow: "rgba(59,130,246,0.15)",
    text: "text-blue-500",
    bg: "bg-blue-500/5 hover:bg-blue-500/10",
    iconBg: "bg-blue-600/10 text-blue-400 border border-blue-500/20",
  },
  linkedin: {
    glow: "rgba(10,102,194,0.15)",
    text: "text-blue-600",
    bg: "bg-blue-600/5 hover:bg-blue-600/10",
    iconBg: "bg-blue-700/10 text-blue-500 border border-blue-500/20",
  },
};

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

  const connectedCount = targets.filter((target) => credentials?.platforms[target.platform]?.ready).length;

  return (
    <section className="grid gap-6 xl:grid-cols-[1fr_420px]">
      {/* Channels Main Panel */}
      <div className="rounded-[32px] border border-white/[0.08] bg-surface/30 p-6 backdrop-blur-md">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between border-b border-white/[0.06] pb-6">
          <div>
            <h3 className="text-2xl font-semibold tracking-[-0.03em] text-white">
              Connect <span className="font-editorial italic font-normal text-cyan">channels</span>
            </h3>
            <p className="mt-1.5 text-sm text-zinc-400 max-w-xl leading-relaxed">
              Link your social network accounts to establish default publication pipelines. The final step is managed cleanly via the Content Schedule.
            </p>
          </div>
          <span className="inline-flex rounded-full border border-cyan/[0.25] bg-teal/[0.10] px-4 py-1.5 text-xs font-bold text-cyan self-start tracking-wider uppercase">
            {connectedCount}/{targets.length} Connected
          </span>
        </div>

        <div className="mt-6 grid gap-4 sm:grid-cols-2">
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

            const pt = platformThemes[target.platform] || {
              glow: "rgba(255,255,255,0.05)",
              text: "text-white",
              bg: "bg-white/5 hover:bg-white/10",
              iconBg: "bg-black/32 text-white border border-white/10",
            };

            return (
              <div 
                key={target.platform} 
                className={`relative rounded-[26px] border p-5 transition-all duration-300 ${
                  selectedForPublish 
                    ? "border-cyan/[0.30] bg-cyan/[0.03]" 
                    : "border-white/[0.06] bg-black/15 hover:border-white/[0.12] hover:bg-black/24"
                }`}
                style={{
                  boxShadow: selectedForPublish ? `0 12px 30px -10px ${pt.glow}` : "none"
                }}
              >
                {/* Visual glow indicator for active status */}
                {ready && (
                  <div className="absolute top-0 right-0 h-16 w-16 rounded-tr-[26px] bg-radial-gradient from-teal/10 to-transparent pointer-events-none" />
                )}

                <div className="flex items-center justify-between">
                  <div 
                    className={`grid h-12 w-12 place-items-center rounded-2xl ${pt.iconBg} transition-all duration-300`}
                    style={{
                      boxShadow: ready ? `0 0 16px ${pt.glow}` : "none"
                    }}
                  >
                    {getPlatformIcon(target.platform)}
                  </div>
                  <SwitchControl checked={selectedForPublish} disabled={isBusy} label="Auto Target" onChange={() => onTogglePlatform(target.platform)} />
                </div>

                <div className="mt-5">
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-1.5 min-w-0">
                      <h4 className="font-semibold text-base text-white truncate">{platformLabel(target.platform)}</h4>
                      {ready ? (
                        <span className="inline-flex h-2 w-2 rounded-full bg-teal shadow-[0_0_8px_rgba(0,194,183,0.5)] shrink-0" />
                      ) : (
                        <span className="inline-flex h-2 w-2 rounded-full bg-warning shadow-[0_0_8px_rgba(255,145,14,0.5)] shrink-0" />
                      )}
                    </div>
                    <span className={`text-[10px] uppercase font-bold tracking-wider shrink-0 ${ready ? "text-teal" : "text-zinc-500"}`}>
                      {ready ? "Active Token" : "Missing Keys"}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-zinc-400 font-medium truncate">{publicAccountLabel(target)}</p>
                </div>

                <div className="mt-4 flex flex-wrap gap-1.5">
                  <span className="rounded-full border border-white/5 bg-white/[0.03] px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-zinc-500">
                    Mode: <span className="text-zinc-300 font-bold">{formatPlatformMode(target.mode)}</span>
                  </span>
                  <span className={`rounded-full border px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider ${selectedForPublish ? "border-cyan/15 bg-cyan/[0.04] text-cyan" : "border-white/5 bg-white/[0.02] text-zinc-500"}`}>
                    {selectedForPublish ? "Target Active" : "Target Paused"}
                  </span>
                  <span className={`rounded-full border px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider ${ready ? "border-teal/15 bg-teal/[0.04] text-teal" : "border-warning/15 bg-warning/[0.04] text-warning"}`}>
                    {ready ? "Authorized" : "Setup Required"}
                  </span>
                </div>

                {!ready && (
                  <div className="mt-3.5 flex items-start gap-2 rounded-xl border border-warning/[0.12] bg-warning/[0.05] p-3 text-xs leading-relaxed text-warning">
                    <AlertCircle className="h-3.5 w-3.5 shrink-0 mt-0.5" />
                    <span>
                      Required keys missing: {(credential?.missing_keys || []).join(", ") || "credential"}. Connect account to publish.
                    </span>
                  </div>
                )}

                {/* Live publishing monitor box */}
                <div className="mt-4 rounded-2xl border border-white/[0.04] bg-black/32 p-4">
                  <div className="flex items-center justify-between gap-3 border-b border-white/[0.04] pb-2.5 mb-2.5">
                    <span className="text-[10px] uppercase font-bold tracking-wider text-zinc-500">Live Activity Monitor</span>
                    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider ${statusTone(activeAction ? "running" : latest?.status || "pending")}`}>
                      {activeAction ? <Loader2 className="h-2.5 w-2.5 shrink-0 animate-spin" /> : null}
                      <span className="truncate">{activeAction?.message || cleanPublishStatus(latest?.status)}</span>
                    </span>
                  </div>
                  {recovery ? (
                    <p className="text-[11px] leading-relaxed text-danger/90">
                      {recovery}
                    </p>
                  ) : (
                    <p className="text-[11px] leading-relaxed text-zinc-500 font-medium">
                      {activeAction ? "Pipeline transmission in progress. Do not refresh." : "Waiting for next schedule slot or due release."}
                    </p>
                  )}
                  {activeAction && (
                    <div className="mt-3 h-1 overflow-hidden rounded-full bg-white/[0.04]">
                      <div className="h-full w-2/3 animate-pulse rounded-full bg-cyan" />
                    </div>
                  )}
                </div>

                <div className="mt-4 flex items-center gap-2">
                  <button
                    type="button"
                    disabled={isBusy}
                    onClick={() => onTestConnection(target.platform)}
                    className="inline-flex h-10 flex-1 items-center justify-center gap-1.5 rounded-full border border-cyan/[0.24] bg-teal/[0.06] text-xs font-bold uppercase tracking-wider text-cyan transition-all hover:bg-teal/[0.12] disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    {actionStates[`test:${target.platform}`]?.status === "running" ? (
                      <>
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        <span>Testing...</span>
                      </>
                    ) : (
                      <>
                        <Wifi className="h-3.5 w-3.5" />
                        <span>Test Connection</span>
                      </>
                    )}
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

      {/* Sidebar Info Panel */}
      <div className="rounded-[32px] border border-white/[0.08] bg-surface/30 p-6 backdrop-blur-md xl:self-start">
        <h3 className="text-lg font-semibold text-white tracking-[-0.02em]">
          Channel <span className="font-editorial italic font-normal text-cyan">readiness</span>
        </h3>
        <p className="mt-1.5 text-xs text-zinc-400 leading-relaxed">
          Authorized pipelines automate content distribution. Monitor and re-authenticate targets from this control panel.
        </p>
        
        <div className="mt-6 grid gap-4">
          <div className="rounded-[22px] border border-cyan/[0.18] bg-teal/[0.06] p-4 text-xs leading-relaxed text-zinc-300">
            <span className="font-bold text-cyan block mb-1">💡 System Tip</span>
            All posts set for auto-publish are safely managed by active background worker threads. To distribute instantly, navigate to the Content Schedule.
          </div>

          <div className="rounded-[22px] border border-white/[0.06] bg-black/20 p-4">
            <p className="text-[10px] uppercase font-bold tracking-wider text-zinc-500 mb-3">Live Default pipelines</p>
            <div className="grid gap-2">
              {targets.map((target) => {
                const ready = credentials?.platforms[target.platform]?.ready;
                const enabled = selectedPlatforms.includes(target.platform);
                return (
                  <div key={target.platform}>
                    {renderReadinessLine(Boolean(ready && enabled), platformLabel(target.platform), !enabled ? "Target Disabled" : ready ? "Authorized & Active" : "Requires Authentication")}
                  </div>
                );
              })}
            </div>
          </div>

          {Array.from(latestByPlatform.values()).length ? (
            <div className="grid gap-2.5">
              <p className="text-[10px] uppercase font-bold tracking-wider text-zinc-500 px-1">Recent publication logs</p>
              {Array.from(latestByPlatform.values()).map((attempt) => (
                <div key={attempt.id} className="rounded-2xl border border-white/[0.04] bg-black/15 p-3.5 transition-colors hover:bg-black/25">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-xs font-bold text-white">{platformLabel(attempt.platform)}</p>
                    <span className={`rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${statusTone(attempt.status)}`}>
                      {cleanPublishStatus(attempt.status)}
                    </span>
                  </div>
                  {attempt.error && (
                    <p className="mt-2 text-[11px] leading-relaxed text-danger/80">
                      {publishActionHint(attempt.error)}
                    </p>
                  )}
                </div>
              ))}
            </div>
          ) : (
            renderEmptyState("No channel logs", "All platform tests and automated schedule distributions will log historical details here.")
          )}
        </div>
      </div>
    </section>
  );
}
