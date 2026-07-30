"use client";

import {AlertCircle, Facebook, HelpCircle, Instagram, Linkedin, Loader2, MoreHorizontal, Send, Wifi, Youtube} from "lucide-react";
import {type FormEvent, type ReactNode, useState} from "react";
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
        {ready ? <MenuAction onClick={() => onTestConnection(platform)}>Test connection</MenuAction> : null}
        {supportsOauth && ready ? <MenuAction onClick={() => onStartOauth(platform)}>Reconnect account</MenuAction> : null}
        <MenuAction danger onClick={() => onDisconnect(platform)}>
          Disconnect
        </MenuAction>
      </div>
    </details>
  );
}

function getPlatformIcon(platform: string) {
  switch (platform) {
    case "youtube":
    case "youtube_shorts":
      return <Youtube className="h-5 w-5" />;
    case "instagram":
    case "instagram_reels":
      return <Instagram className="h-5 w-5" />;
    case "facebook":
    case "facebook_reels":
      return <Facebook className="h-5 w-5" />;
    case "linkedin":
      return <Linkedin className="h-5 w-5" />;
    case "telegram_channel":
      return <Send className="h-5 w-5" />;
    case "tiktok":
      return (
        <svg className="h-5 w-5 fill-current" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
          <path d="M12.53.02C13.84 0 15.14.01 16.44 0c.08 1.53.63 3.09 1.75 4.17 1.12 1.11 2.7 1.62 4.24 1.79v4.03c-1.44-.05-2.89-.54-3.99-1.52-.28-.25-.53-.53-.76-.83v6.24c0 1.62-.35 3.26-1.19 4.6-1.12 1.83-3.13 3.12-5.32 3.38-2.23.27-4.63-.33-6.26-1.92C3.34 18.23 2.5 15.65 2.87 13.1c.33-2.3 1.73-4.48 3.86-5.46 1.4-.64 2.98-.82 4.49-.55v4.17c-1.13-.3-2.38-.11-3.32.55-1 .71-1.55 1.99-1.48 3.23.05 1.08.64 2.1 1.53 2.65.9.56 2.06.63 3.01.2 1.03-.47 1.73-1.54 1.73-2.67V.02h-.16z" />
        </svg>
      );
    default:
      return <HelpCircle className="h-5 w-5" />;
  }
}

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
    text: "text-blue-400",
    bg: "bg-blue-500/5 hover:bg-blue-500/10",
    iconBg: "bg-blue-600/10 text-blue-400 border border-blue-500/20",
  },
  linkedin: {
    glow: "rgba(14,165,233,0.15)",
    text: "text-sky-400",
    bg: "bg-sky-500/5 hover:bg-sky-500/10",
    iconBg: "bg-sky-600/10 text-sky-400 border border-sky-500/20",
  },
};
platformThemes.youtube_shorts = platformThemes.youtube;
platformThemes.facebook_reels = platformThemes.facebook;
platformThemes.instagram_reels = platformThemes.instagram;
platformThemes.telegram_channel = {
  glow: "rgba(56,189,248,0.15)",
  text: "text-sky-400",
  bg: "bg-sky-500/5 hover:bg-sky-500/10",
  iconBg: "bg-sky-600/10 text-sky-400 border border-sky-500/20",
};

function TelegramConnectForm({
  disabled,
  saving,
  onSave,
}: {
  disabled?: boolean;
  saving?: boolean;
  onSave: (values: Record<string, string>) => void;
}) {
  const [botToken, setBotToken] = useState("");
  const [channelId, setChannelId] = useState("");

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const token = botToken.trim();
    const channel = channelId.trim();
    if (!token || !channel) return;
    onSave({
      TELEGRAM_BOT_TOKEN: token,
      TELEGRAM_CHANNEL_ID: channel,
      TELEGRAM_CHAT_ID: channel,
    });
  }

  return (
    <form onSubmit={handleSubmit} className="mt-3.5 grid gap-2.5 rounded-xl border border-cyan/[0.14] bg-cyan/[0.04] p-3">
      <p className="text-xs leading-relaxed text-zinc-300">Paste your bot token and channel (or chat) id for this workspace.</p>
      <label className="grid gap-1 text-[11px] font-semibold uppercase tracking-wider text-zinc-500">
        Bot token
        <input
          type="password"
          autoComplete="off"
          value={botToken}
          disabled={disabled || saving}
          onChange={(event) => setBotToken(event.target.value)}
          placeholder="123456:ABC…"
          className="h-10 rounded-xl border border-white/[0.08] bg-black/30 px-3 text-sm font-normal normal-case tracking-normal text-white outline-none focus:border-cyan/40"
        />
      </label>
      <label className="grid gap-1 text-[11px] font-semibold uppercase tracking-wider text-zinc-500">
        Channel or chat id
        <input
          type="text"
          autoComplete="off"
          value={channelId}
          disabled={disabled || saving}
          onChange={(event) => setChannelId(event.target.value)}
          placeholder="@mychannel or -100…"
          className="h-10 rounded-xl border border-white/[0.08] bg-black/30 px-3 text-sm font-normal normal-case tracking-normal text-white outline-none focus:border-cyan/40"
        />
      </label>
      <button
        type="submit"
        disabled={disabled || saving || !botToken.trim() || !channelId.trim()}
        className="inline-flex h-10 items-center justify-center gap-1.5 rounded-full border border-cyan/[0.28] bg-teal/[0.12] text-xs font-bold uppercase tracking-wider text-cyan transition-all hover:bg-teal/[0.18] disabled:cursor-not-allowed disabled:opacity-40"
      >
        {saving ? (
          <>
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            <span>Saving…</span>
          </>
        ) : (
          <span>Save &amp; connect</span>
        )}
      </button>
    </form>
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
  onSaveCredentials,
  onUpdateDelivery,
  publicAccountLabel,
  publishActionHint,
  formatPlatformMode,
  cleanPublishStatus,
  statusTone,
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
  onSaveCredentials?: (platform: string, values: Record<string, string>) => void;
  onUpdateDelivery?: (target: PublishTarget, patch: {daily_cap?: number; enabled?: boolean; mode?: string}) => void;
  publicAccountLabel: (target: PublishTarget) => string;
  publishActionHint: (error?: string) => string;
  formatPlatformMode: (mode?: string) => string;
  cleanPublishStatus: (status?: string) => string;
  statusTone: (status: string) => string;
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
      <div className="rounded-[32px] border border-white/[0.08] bg-surface/30 p-6 backdrop-blur-md">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between border-b border-white/[0.06] pb-6">
          <div>
            <h3 className="text-2xl font-semibold tracking-[-0.03em] text-white">
              Connect <span className="font-editorial italic font-normal text-cyan">publish accounts</span>
            </h3>
            <p className="mt-1.5 text-sm text-zinc-400 max-w-xl leading-relaxed">
              Link Facebook, YouTube, TikTok, or Telegram for this workspace. This is where clips publish — not the same as watching a YouTube source on Create.
            </p>
          </div>
          <span className="inline-flex rounded-full border border-cyan/[0.25] bg-teal/[0.10] px-4 py-1.5 text-xs font-bold text-cyan self-start tracking-wider uppercase">
            {connectedCount}/{targets.length} Connected
          </span>
        </div>

        <div className="mt-6 grid gap-4 sm:grid-cols-2">
          {targets.length === 0
            ? renderEmptyState(
                "No publish destinations yet",
                "This workspace has no platform rows yet. Load destinations to auto-seed Facebook, YouTube, TikTok, and Telegram — then connect each account.",
              )
            : null}
          {targets.map((target) => {
            const ready = Boolean(credentials?.platforms[target.platform]?.ready);
            const credential = credentials?.platforms[target.platform];
            const selectedForPublish = selectedPlatforms.includes(target.platform);
            const latest = latestByPlatform.get(target.platform);
            const recovery = publishActionHint(latest?.error);
            const supportsOauth = oauthPlatforms.has(target.platform);
            const isTelegram = target.platform === "telegram_channel";
            const activeAction = [
              actionStates[`test:${target.platform}`],
              actionStates[`connect:${target.platform}`],
              actionStates[`credentials:${target.platform}`],
              actionStates[`disconnect:${target.platform}`],
              actionStates[`target:${target.platform}`],
            ].find((item) => item?.status === "running");
            const isBusy = Boolean(activeAction);
            const connectRunning = actionStates[`connect:${target.platform}`]?.status === "running";
            const credentialsRunning = actionStates[`credentials:${target.platform}`]?.status === "running";
            const testRunning = actionStates[`test:${target.platform}`]?.status === "running";

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
                  selectedForPublish ? "border-cyan/[0.30] bg-cyan/[0.03]" : "border-white/[0.06] bg-black/15 hover:border-white/[0.12] hover:bg-black/24"
                }`}
                style={{
                  boxShadow: selectedForPublish ? `0 12px 30px -10px ${pt.glow}` : "none",
                }}
              >
                {ready ? <div className="absolute top-0 right-0 h-16 w-16 rounded-tr-[26px] bg-radial-gradient from-teal/10 to-transparent pointer-events-none" /> : null}

                <div className="flex items-center justify-between">
                  <div
                    className={`grid h-12 w-12 place-items-center rounded-2xl ${pt.iconBg} transition-all duration-300`}
                    style={{
                      boxShadow: ready ? `0 0 16px ${pt.glow}` : "none",
                    }}
                  >
                    {getPlatformIcon(target.platform)}
                  </div>
                  <SwitchControl checked={selectedForPublish} disabled={isBusy} label="Auto publish" onChange={() => onTogglePlatform(target.platform)} />
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
                      {ready ? "Connected" : "Not connected"}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-zinc-400 font-medium truncate">{publicAccountLabel(target)}</p>
                </div>

                <div className="mt-3 flex flex-wrap gap-1.5">
                  <span
                    className={`rounded-full border px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider ${
                      ready ? "border-teal/15 bg-teal/[0.04] text-teal" : "border-warning/15 bg-warning/[0.04] text-warning"
                    }`}
                  >
                    {ready ? "Ready to publish" : "Connect to publish"}
                  </span>
                  <span
                    className={`rounded-full border px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider ${
                      selectedForPublish ? "border-cyan/15 bg-cyan/[0.04] text-cyan" : "border-white/5 bg-white/[0.02] text-zinc-500"
                    }`}
                  >
                    {selectedForPublish ? "In rotation" : "Paused"}
                  </span>
                </div>

                {!ready && supportsOauth ? (
                  <div className="mt-3.5 flex items-start gap-2 rounded-xl border border-white/[0.06] bg-black/20 p-3 text-xs leading-relaxed text-zinc-400">
                    <AlertCircle className="h-3.5 w-3.5 shrink-0 mt-0.5 text-cyan" />
                    <span>Sign in with {platformLabel(target.platform)} to authorize publishing for this workspace.</span>
                  </div>
                ) : null}

                {!ready && isTelegram && onSaveCredentials ? (
                  <TelegramConnectForm
                    disabled={isBusy}
                    saving={credentialsRunning}
                    onSave={(values) => onSaveCredentials(target.platform, values)}
                  />
                ) : null}

                {!ready && !supportsOauth && !isTelegram ? (
                  <div className="mt-3.5 flex items-start gap-2 rounded-xl border border-white/[0.06] bg-black/20 p-3 text-xs leading-relaxed text-zinc-400">
                    <AlertCircle className="h-3.5 w-3.5 shrink-0 mt-0.5 text-cyan" />
                    <span>Connect this account before publishing. Use the button below when setup is available.</span>
                  </div>
                ) : null}

                {credential?.missing_keys?.length && !ready ? (
                  <details className="mt-2">
                    <summary className="cursor-pointer text-[11px] font-medium text-zinc-500 hover:text-zinc-300">Show technical details</summary>
                    <p className="mt-1.5 break-all text-[11px] leading-relaxed text-zinc-500">{credential.missing_keys.join(", ")}</p>
                  </details>
                ) : null}

                {ready && onUpdateDelivery ? (
                  <details className="mt-4 border-t border-white/[0.06] pt-3">
                    <summary className="cursor-pointer text-[11px] font-semibold uppercase tracking-wider text-zinc-500 hover:text-zinc-300">
                      Delivery settings · {formatPlatformMode(target.mode)}
                    </summary>
                    <div className="mt-3 flex flex-wrap items-center gap-3">
                      <label className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-zinc-500">
                        Posts / day
                        <input
                          type="number"
                          min={0}
                          max={50}
                          defaultValue={target.daily_cap}
                          key={`${target.id}-${target.daily_cap}`}
                          onBlur={(event) => {
                            const next = Number(event.target.value);
                            if (!Number.isFinite(next) || next === target.daily_cap) return;
                            onUpdateDelivery(target, {daily_cap: Math.max(0, Math.min(50, Math.round(next)))});
                          }}
                          className="h-8 w-16 rounded-xl border border-white/[0.08] bg-black/30 px-2 text-sm text-white outline-none focus:border-cyan/40"
                        />
                      </label>
                      <button
                        type="button"
                        disabled={isBusy}
                        onClick={() => onUpdateDelivery(target, {enabled: !(target.enabled ?? true)})}
                        className="rounded-full border border-white/[0.08] px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider text-zinc-400 hover:text-cyan"
                      >
                        {(target.enabled ?? true) ? "Disable delivery" : "Enable delivery"}
                      </button>
                    </div>
                  </details>
                ) : null}

                {ready ? (
                  <details className="mt-3">
                    <summary className="cursor-pointer text-[11px] font-semibold uppercase tracking-wider text-zinc-500 hover:text-zinc-300">
                      Recent activity · {cleanPublishStatus(latest?.status)}
                    </summary>
                    <div className="mt-2 rounded-2xl border border-white/[0.04] bg-black/32 p-3">
                      {recovery ? (
                        <p className="text-[11px] leading-relaxed text-danger/90">{recovery}</p>
                      ) : (
                        <p className="text-[11px] leading-relaxed text-zinc-500 font-medium">
                          {activeAction ? activeAction.message : "Waiting for the next scheduled publish."}
                        </p>
                      )}
                    </div>
                  </details>
                ) : null}

                <div className="mt-4 flex items-center gap-2">
                  {supportsOauth && !ready ? (
                    <button
                      type="button"
                      disabled={isBusy}
                      onClick={() => onStartOauth(target.platform)}
                      className="inline-flex h-10 flex-1 items-center justify-center gap-1.5 rounded-full border border-cyan/[0.28] bg-teal/[0.12] text-xs font-bold uppercase tracking-wider text-cyan transition-all hover:bg-teal/[0.18] disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      {connectRunning ? (
                        <>
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          <span>Connecting…</span>
                        </>
                      ) : (
                        <span>Connect account</span>
                      )}
                    </button>
                  ) : null}

                  {ready ? (
                    <button
                      type="button"
                      disabled={isBusy}
                      onClick={() => onTestConnection(target.platform)}
                      className="inline-flex h-10 flex-1 items-center justify-center gap-1.5 rounded-full border border-cyan/[0.24] bg-teal/[0.06] text-xs font-bold uppercase tracking-wider text-cyan transition-all hover:bg-teal/[0.12] disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      {testRunning ? (
                        <>
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          <span>Testing…</span>
                        </>
                      ) : (
                        <>
                          <Wifi className="h-3.5 w-3.5" />
                          <span>Test connection</span>
                        </>
                      )}
                    </button>
                  ) : null}

                  {!supportsOauth && !ready && !isTelegram ? (
                    <div className="flex-1" />
                  ) : null}

                  <PlatformActionMenu
                    disabled={isBusy}
                    ready={ready}
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

      <div className="rounded-[32px] border border-white/[0.08] bg-surface/30 p-6 backdrop-blur-md xl:self-start">
        <h3 className="text-lg font-semibold text-white tracking-[-0.02em]">
          Account <span className="font-editorial italic font-normal text-cyan">status</span>
        </h3>
        <p className="mt-1.5 text-xs text-zinc-400 leading-relaxed">
          Connect each destination once per workspace. Reconnect anytime if a token expires.
        </p>

        <div className="mt-6 grid gap-4">
          <div className="rounded-[22px] border border-cyan/[0.18] bg-teal/[0.06] p-4 text-xs leading-relaxed text-zinc-300">
            <span className="font-bold text-cyan block mb-1">Tip</span>
            After connecting, keep Auto publish on for platforms you want in the schedule rotation. Fine-tune posts/day under Delivery settings on each connected card.
          </div>

          <div className="rounded-[22px] border border-white/[0.06] bg-black/20 p-4">
            <p className="text-[10px] uppercase font-bold tracking-wider text-zinc-500 mb-3">Destinations</p>
            <div className="grid gap-2">
              {targets.map((target) => {
                const ready = credentials?.platforms[target.platform]?.ready;
                const enabled = selectedPlatforms.includes(target.platform);
                return (
                  <div key={target.platform}>
                    {renderReadinessLine(
                      Boolean(ready && enabled),
                      platformLabel(target.platform),
                      !ready ? "Not connected" : !enabled ? "Connected · paused" : "Connected · in rotation",
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {Array.from(latestByPlatform.values()).length ? (
            <div className="grid gap-2.5">
              <p className="text-[10px] uppercase font-bold tracking-wider text-zinc-500 px-1">Recent publish logs</p>
              {Array.from(latestByPlatform.values()).map((attempt) => (
                <div key={attempt.id} className="rounded-2xl border border-white/[0.04] bg-black/15 p-3.5 transition-colors hover:bg-black/25">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-xs font-bold text-white">{platformLabel(attempt.platform)}</p>
                    <span className={`rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${statusTone(attempt.status)}`}>
                      {cleanPublishStatus(attempt.status)}
                    </span>
                  </div>
                  {attempt.error ? <p className="mt-2 text-[11px] leading-relaxed text-danger/80">{publishActionHint(attempt.error)}</p> : null}
                </div>
              ))}
            </div>
          ) : (
            renderEmptyState("No publish logs yet", "Connection tests and scheduled publishes will show up here.")
          )}
        </div>
      </div>
    </section>
  );
}
