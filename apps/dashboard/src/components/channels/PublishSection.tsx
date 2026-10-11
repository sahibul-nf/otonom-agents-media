"use client";

import {Facebook, HelpCircle, Instagram, Linkedin, Loader2, MoreHorizontal, Send, Wifi, Youtube} from "lucide-react";
import {type FormEvent, type ReactNode, useState} from "react";
import {EmptyState, RecoveryAction} from "@/components/shared/StudioPrimitives";
import {disabledPublishPlatformReason, isPublishPlatformDisabled} from "@/lib/publish-platforms";
import {classifyPublishError} from "@/lib/publish-recovery";
import {LlmKeysSection, type LlmStatusPayload} from "@/components/channels/LlmKeysSection";
import {platformLabel, type CredentialStatus, type PostizIntegration, type PublishAttempt, type PublishTarget} from "@/lib/media-api";

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
  onMapPostiz,
}: {
  disabled?: boolean;
  ready: boolean;
  supportsOauth: boolean;
  platform: string;
  onTestConnection: (platform: string) => void;
  onStartOauth: (platform: string) => void;
  onDisconnect: (platform: string) => void;
  onMapPostiz?: () => void;
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
        {onMapPostiz ? <MenuAction onClick={onMapPostiz}>Map Postiz channel</MenuAction> : null}
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
    case "youtube_video":
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
platformThemes.youtube_video = platformThemes.youtube;
platformThemes.facebook_reels = platformThemes.facebook;
platformThemes.instagram_reels = platformThemes.instagram;
platformThemes.telegram_channel = {
  glow: "rgba(56,189,248,0.15)",
  text: "text-sky-400",
  bg: "bg-sky-500/5 hover:bg-sky-500/10",
  iconBg: "bg-sky-600/10 text-sky-400 border border-sky-500/20",
};

function TelegramConnectDialog({
  open,
  saving,
  onClose,
  onSave,
}: {
  open: boolean;
  saving?: boolean;
  onClose: () => void;
  onSave: (values: Record<string, string>) => void | Promise<void>;
}) {
  const [botToken, setBotToken] = useState("");
  const [channelId, setChannelId] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (!open) return null;

  const busy = saving || submitting;
  const canSubmit = Boolean(botToken.trim() && channelId.trim()) && !busy;

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const token = botToken.trim();
    const channel = channelId.trim();
    if (!token || !channel || busy) return;
    setSubmitting(true);
    try {
      await onSave({
        TELEGRAM_BOT_TOKEN: token,
        TELEGRAM_CHANNEL_ID: channel,
        TELEGRAM_CHAT_ID: channel,
      });
      setBotToken("");
      setChannelId("");
      onClose();
    } catch {
      // Parent surfaces the error toast/status.
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-[60] grid place-items-center bg-black/60 px-4 backdrop-blur-sm" role="dialog" aria-modal="true" aria-labelledby="telegram-connect-title">
      <button type="button" aria-label="Close dialog" className="absolute inset-0 cursor-default" onClick={onClose} />
      <form
        onSubmit={(event) => void handleSubmit(event)}
        className="relative z-10 w-full max-w-md rounded-[28px] border border-white/[0.10] bg-surface p-5 shadow-2xl"
      >
        <div className="mb-4 grid h-12 w-12 place-items-center rounded-2xl bg-teal/[0.14] text-cyan">
          <Send className="h-5 w-5" />
        </div>
        <h3 id="telegram-connect-title" className="text-xl font-semibold text-white">
          Connect Telegram
        </h3>
        <p className="mt-2 text-sm leading-6 text-zinc-400">Enter the bot token and channel (or chat) id for this workspace.</p>

        <div className="mt-5 grid gap-3">
          <label className="grid gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-zinc-500">
            Bot token
            <input
              type="password"
              autoComplete="off"
              data-autofocus
              value={botToken}
              disabled={busy}
              onChange={(event) => setBotToken(event.target.value)}
              placeholder="123456:ABC…"
              className="h-11 rounded-xl border border-white/[0.08] bg-black/30 px-3 text-sm font-normal normal-case tracking-normal text-white outline-none focus:border-cyan/40"
            />
          </label>
          <label className="grid gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-zinc-500">
            Channel or chat id
            <input
              type="text"
              autoComplete="off"
              value={channelId}
              disabled={busy}
              onChange={(event) => setChannelId(event.target.value)}
              placeholder="@mychannel or -100…"
              className="h-11 rounded-xl border border-white/[0.08] bg-black/30 px-3 text-sm font-normal normal-case tracking-normal text-white outline-none focus:border-cyan/40"
            />
          </label>
        </div>

        <div className="mt-6 grid gap-2 sm:grid-cols-2">
          <button type="button" onClick={onClose} disabled={busy} className="h-11 rounded-full border border-white/[0.10] text-sm font-semibold text-zinc-300 hover:bg-white/[0.04] disabled:opacity-40">
            Cancel
          </button>
          <button
            type="submit"
            disabled={!canSubmit}
            className="inline-flex h-11 items-center justify-center gap-1.5 rounded-full bg-cyan text-sm font-semibold text-ink disabled:cursor-not-allowed disabled:opacity-40"
          >
            {busy ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                <span>Saving…</span>
              </>
            ) : (
              <span>Save &amp; connect</span>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}

function PostizConnectDialog({
  open,
  saving,
  defaultUrl,
  onClose,
  onSave,
}: {
  open: boolean;
  saving?: boolean;
  defaultUrl: string;
  onClose: () => void;
  onSave: (values: {api_url: string; api_key: string}) => void | Promise<void>;
}) {
  const [apiUrl, setApiUrl] = useState(defaultUrl);
  const [apiKey, setApiKey] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (!open) return null;

  const busy = saving || submitting;
  const canSubmit = Boolean(apiKey.trim()) && !busy;

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!canSubmit) return;
    setSubmitting(true);
    try {
      await onSave({api_url: apiUrl.trim() || defaultUrl, api_key: apiKey.trim()});
      setApiKey("");
      onClose();
    } catch {
      // Parent surfaces the error.
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-[60] grid place-items-center bg-black/60 px-4 backdrop-blur-sm" role="dialog" aria-modal="true" aria-labelledby="postiz-connect-title">
      <form onSubmit={handleSubmit} className="w-full max-w-md rounded-[28px] border border-white/[0.10] bg-surface-panel p-6 shadow-2xl">
        <h3 id="postiz-connect-title" className="text-xl font-semibold text-white">
          Connect Postiz
        </h3>
        <p className="mt-2 text-sm text-zinc-400">
          Reveal + copy the key from Postiz Settings → Public API. Default host is the API subdomain; Connect also tries{" "}
          <span className="text-zinc-300">postiz.nourdaily.com/api/public/v1</span>.
        </p>
        <label className="mt-5 block text-[11px] font-semibold uppercase tracking-wider text-zinc-500">
          API URL
          <input
            value={apiUrl}
            onChange={(event) => setApiUrl(event.target.value)}
            placeholder={defaultUrl}
            className="mt-1.5 h-11 w-full rounded-2xl border border-white/[0.08] bg-black/30 px-3 text-sm text-white outline-none focus:border-cyan/40"
          />
        </label>
        <label className="mt-4 block text-[11px] font-semibold uppercase tracking-wider text-zinc-500">
          API key
          <input
            type="password"
            value={apiKey}
            onChange={(event) => setApiKey(event.target.value)}
            autoComplete="off"
            className="mt-1.5 h-11 w-full rounded-2xl border border-white/[0.08] bg-black/30 px-3 text-sm text-white outline-none focus:border-cyan/40"
          />
        </label>
        <div className="mt-6 flex justify-end gap-2">
          <button type="button" onClick={onClose} className="h-11 rounded-full px-4 text-xs font-bold uppercase tracking-wider text-zinc-400">
            Cancel
          </button>
          <button
            type="submit"
            disabled={!canSubmit}
            className="inline-flex h-11 items-center gap-2 rounded-full bg-cyan px-5 text-xs font-bold uppercase tracking-wider text-ink disabled:opacity-40"
          >
            {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
            Connect
          </button>
        </div>
      </form>
    </div>
  );
}

function PostizMapDialog({
  open,
  platform,
  saving,
  integrations,
  loading,
  onClose,
  onSave,
}: {
  open: boolean;
  platform: string;
  saving?: boolean;
  integrations: PostizIntegration[];
  loading?: boolean;
  onClose: () => void;
  onSave: (integration: PostizIntegration | null) => void | Promise<void>;
}) {
  const [selected, setSelected] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (!open) return null;

  const busy = saving || submitting;

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const match = integrations.find((item) => item.id === selected) || null;
    if (!match || busy) return;
    setSubmitting(true);
    try {
      await onSave(match);
      onClose();
    } catch {
      // Parent surfaces the error.
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-[60] grid place-items-center bg-black/60 px-4 backdrop-blur-sm" role="dialog" aria-modal="true">
      <form onSubmit={handleSubmit} className="w-full max-w-md rounded-[28px] border border-white/[0.10] bg-surface-panel p-6 shadow-2xl">
        <h3 className="text-xl font-semibold text-white">Map {platformLabel(platform)}</h3>
        <p className="mt-2 text-sm text-zinc-400">Pick the Postiz channel that should receive this destination.</p>
        <select
          value={selected}
          onChange={(event) => setSelected(event.target.value)}
          disabled={loading || busy}
          className="mt-5 h-11 w-full rounded-2xl border border-white/[0.08] bg-black/30 px-3 text-sm text-white outline-none focus:border-cyan/40"
        >
          <option value="">{loading ? "Loading channels…" : "Select a channel"}</option>
          {integrations.map((item) => (
            <option key={item.id} value={item.id} disabled={item.disabled}>
              {item.name}
              {item.identifier ? ` · ${item.identifier}` : ""}
            </option>
          ))}
        </select>
        <div className="mt-6 flex justify-end gap-2">
          <button type="button" onClick={onClose} className="h-11 rounded-full px-4 text-xs font-bold uppercase tracking-wider text-zinc-400">
            Cancel
          </button>
          <button
            type="submit"
            disabled={!selected || busy}
            className="h-11 rounded-full bg-cyan px-5 text-xs font-bold uppercase tracking-wider text-ink disabled:opacity-40"
          >
            Save map
          </button>
        </div>
      </form>
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
  onSaveCredentials,
  onConnectPostiz,
  onDisconnectPostiz,
  onMapPostiz,
  onLoadPostizIntegrations,
  onUpdateDelivery,
  onRefresh,
  profileId,
  onSaveLlm,
  onConnectLlmConnector,
  onSelectLlmModel,
  onSaveLlmRouting,
  onTestLlmAgent,
  llmStatus,
  llmStatusLoading,
  publicAccountLabel,
  publishActionHint,
  formatPlatformMode,
  cleanPublishStatus,
  statusTone,
}: {
  targets: PublishTarget[];
  profileId: string;
  onSaveLlm?: (values: Record<string, string>) => void | Promise<void>;
  onConnectLlmConnector?: (connectorId: string, action?: "connect" | "activate" | "deactivate") => void | Promise<void>;
  onSelectLlmModel?: (connectorId: string, modelId: string) => void | Promise<void>;
  onSaveLlmRouting?: (primary: string, fallbacks: string[]) => void | Promise<void>;
  onTestLlmAgent?: () => void | Promise<void>;
  llmStatus?: LlmStatusPayload | null;
  llmStatusLoading?: boolean;
  credentials: CredentialStatus | null;
  attempts: PublishAttempt[];
  selectedPlatforms: string[];
  actionStates: Record<string, ActionUiState>;
  oauthPlatforms: Set<string>;
  onTogglePlatform: (platform: string) => void;
  onTestConnection: (platform: string) => void;
  onStartOauth: (platform: string) => void;
  onDisconnect: (platform: string) => void;
  onSaveCredentials?: (platform: string, values: Record<string, string>) => void | Promise<void>;
  onConnectPostiz?: (values: {api_url: string; api_key: string}) => void | Promise<void>;
  onDisconnectPostiz?: () => void | Promise<void>;
  onMapPostiz?: (platform: string, integration: PostizIntegration | null) => void | Promise<void>;
  onLoadPostizIntegrations?: (platform: string) => Promise<PostizIntegration[]>;
  onUpdateDelivery?: (target: PublishTarget, patch: {daily_cap?: number; enabled?: boolean; mode?: string}) => void;
  onRefresh?: () => void;
  publicAccountLabel: (target: PublishTarget) => string;
  publishActionHint: (error?: string) => string;
  formatPlatformMode: (mode?: string) => string;
  cleanPublishStatus: (status?: string) => string;
  statusTone: (status: string) => string;
}) {
  const [publishPane, setPublishPane] = useState<"accounts" | "models">("accounts");
  const [telegramDialogOpen, setTelegramDialogOpen] = useState(false);
  const [postizDialogOpen, setPostizDialogOpen] = useState(false);
  const [mapPlatform, setMapPlatform] = useState("");
  const [mapIntegrations, setMapIntegrations] = useState<PostizIntegration[]>([]);
  const [mapLoading, setMapLoading] = useState(false);
  const latestByPlatform = new Map<string, PublishAttempt>();
  for (const attempt of attempts) {
    if (!latestByPlatform.has(attempt.platform)) latestByPlatform.set(attempt.platform, attempt);
  }

  const connectableTargets = targets.filter((target) => !isPublishPlatformDisabled(target.platform));
  const connectedCount = connectableTargets.filter((target) => credentials?.platforms[target.platform]?.ready).length;
  const recentLogs = Array.from(latestByPlatform.values());
  const telegramSaving = actionStates["credentials:telegram_channel"]?.status === "running";
  const postizSaving = actionStates["postiz:connect"]?.status === "running";
  const postizConnected = Boolean(credentials?.postiz?.connected);
  const postizOrigin = credentials?.postiz?.api_origin || "https://api-postiz.nourdaily.com";

  async function openMap(platform: string) {
    setMapPlatform(platform);
    setMapIntegrations([]);
    if (!onLoadPostizIntegrations) return;
    setMapLoading(true);
    try {
      setMapIntegrations(await onLoadPostizIntegrations(platform));
    } catch {
      setMapIntegrations([]);
    } finally {
      setMapLoading(false);
    }
  }

  return (
    <section className="grid gap-6">
      <div className="flex flex-wrap gap-2" role="tablist" aria-label="Publish setup">
        <button
          type="button"
          role="tab"
          aria-selected={publishPane === "accounts"}
          onClick={() => setPublishPane("accounts")}
          className={`min-h-[44px] rounded-full border px-4 py-2 text-xs font-semibold transition ${
            publishPane === "accounts"
              ? "border-cyan/40 bg-cyan/10 text-cyan"
              : "border-white/[0.08] bg-black/20 text-text-secondary hover:text-text-primary"
          }`}
        >
          Accounts
        </button>
        {onSaveLlm ? (
          <button
            type="button"
            role="tab"
            aria-selected={publishPane === "models"}
            onClick={() => setPublishPane("models")}
            className={`min-h-[44px] rounded-full border px-4 py-2 text-xs font-semibold transition ${
              publishPane === "models"
                ? "border-cyan/40 bg-cyan/10 text-cyan"
                : "border-white/[0.08] bg-black/20 text-text-secondary hover:text-text-primary"
            }`}
          >
            Models
          </button>
        ) : null}
      </div>

      {publishPane === "models" && onSaveLlm ? (
        <LlmKeysSection
          credentials={credentials}
          profileId={profileId}
          llmStatus={llmStatus ?? null}
          llmStatusLoading={llmStatusLoading}
          actionStates={actionStates}
          onSaveLlm={onSaveLlm}
          onConnectConnector={onConnectLlmConnector}
          onSelectModel={onSelectLlmModel}
          onSaveRouting={onSaveLlmRouting}
          onTestAgent={onTestLlmAgent}
        />
      ) : null}

      {publishPane === "accounts" ? (
    <div className="grid gap-6 xl:grid-cols-[1fr_360px]">
      <div className="rounded-[32px] border border-white/[0.08] bg-surface/30 p-6 backdrop-blur-md">
        <div className="flex items-center justify-between gap-3 pb-5 border-b border-white/[0.06]">
          <p className="text-sm text-text-secondary">
            {targets.length === 0
              ? "No destinations yet"
              : `${connectedCount} of ${connectableTargets.length} connected`}
          </p>
        </div>

        <div className="mt-5 rounded-2xl border border-white/[0.08] bg-black/20 p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-white">Postiz delivery</p>
              <p className="mt-1 text-xs text-zinc-400">
                {postizConnected
                  ? "Workspace is connected. Map each destination to a Postiz channel."
                  : "Connect once per workspace. No .env keys — the API key stays in this workspace vault."}
              </p>
            </div>
            {postizConnected ? (
              <button
                type="button"
                onClick={() => onDisconnectPostiz?.()}
                className="rounded-full border border-white/[0.08] px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider text-zinc-400 hover:text-danger"
              >
                Disconnect
              </button>
            ) : (
              <button
                type="button"
                disabled={!onConnectPostiz || postizSaving}
                onClick={() => setPostizDialogOpen(true)}
                className="inline-flex h-9 items-center rounded-full bg-cyan px-4 text-[10px] font-bold uppercase tracking-wider text-ink"
              >
                Connect Postiz
              </button>
            )}
          </div>
        </div>

        <div className="mt-6 grid gap-4 sm:grid-cols-2">
          {targets.length === 0 ? (
            <div className="sm:col-span-2">
              <EmptyState
                title="No publish destinations yet"
                text="Load default destinations for this workspace, then connect each available account."
                actionLabel={onRefresh ? "Load destinations" : undefined}
                onAction={onRefresh}
              />
            </div>
          ) : null}

          {targets.map((target) => {
            const unavailable = isPublishPlatformDisabled(target.platform);
            const unavailableReason =
              credentials?.platforms[target.platform]?.unavailable_reason || disabledPublishPlatformReason(target.platform);
            const ready = !unavailable && Boolean(credentials?.platforms[target.platform]?.ready);
            const selectedForPublish = selectedPlatforms.includes(target.platform);
            const latest = latestByPlatform.get(target.platform);
            const recovery = publishActionHint(latest?.error);
            const latestRecovery = classifyPublishError(latest?.error);
            const supportsOauth = oauthPlatforms.has(target.platform);
            const isTelegram = target.platform === "telegram_channel";
            const postizMapped = Boolean(credentials?.platforms[target.platform]?.postiz_integration_id);
            const showPostizMap = postizConnected && !postizMapped && Boolean(onMapPostiz);
            const activeAction = [
              actionStates[`test:${target.platform}`],
              actionStates[`connect:${target.platform}`],
              actionStates[`credentials:${target.platform}`],
              actionStates[`disconnect:${target.platform}`],
              actionStates[`target:${target.platform}`],
            ].find((item) => item?.status === "running");
            const isBusy = Boolean(activeAction);
            const connectRunning = actionStates[`connect:${target.platform}`]?.status === "running";
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
                  unavailable
                    ? "border-white/[0.05] bg-black/10 opacity-90"
                    : ready && selectedForPublish
                      ? "border-cyan/[0.30] bg-cyan/[0.03]"
                      : "border-white/[0.06] bg-black/15 hover:border-white/[0.12] hover:bg-black/24"
                }`}
                style={{
                  boxShadow: ready && selectedForPublish ? `0 12px 30px -10px ${pt.glow}` : "none",
                }}
              >
                <div className="flex items-start justify-between gap-3">
                  <div
                    className={`grid h-12 w-12 place-items-center rounded-2xl ${pt.iconBg} transition-all duration-300`}
                    style={{boxShadow: ready ? `0 0 16px ${pt.glow}` : "none"}}
                  >
                    {getPlatformIcon(target.platform)}
                  </div>
                  {unavailable ? (
                    <span className="text-[10px] font-bold uppercase tracking-wider text-amber-400/90">Unavailable</span>
                  ) : ready ? (
                    <SwitchControl
                      checked={selectedForPublish}
                      disabled={isBusy}
                      label="Auto publish"
                      onChange={() => onTogglePlatform(target.platform)}
                    />
                  ) : (
                    <span className="text-[10px] font-bold uppercase tracking-wider text-zinc-500">Not connected</span>
                  )}
                </div>

                <div className="mt-4">
                  <div className="flex items-center gap-1.5 min-w-0">
                    <h4 className="font-semibold text-base text-white truncate">{platformLabel(target.platform)}</h4>
                    {ready ? <span className="inline-flex h-2 w-2 rounded-full bg-teal shadow-[0_0_8px_rgba(0,194,183,0.5)] shrink-0" /> : null}
                  </div>
                  <p className={`mt-1 text-xs text-zinc-400 font-medium ${unavailable ? "line-clamp-3" : "truncate"}`}>
                    {unavailable
                      ? unavailableReason
                      : postizMapped
                        ? credentials?.platforms[target.platform]?.postiz_integration_name || "Postiz channel"
                        : postizConnected
                          ? "Map a Postiz channel (required to send via Postiz)"
                          : ready
                            ? publicAccountLabel(target)
                            : "Connect to publish from this workspace"}
                  </p>
                </div>

                {ready && onUpdateDelivery ? (
                  <details className="mt-4 border-t border-white/[0.06] pt-3">
                    <summary className="cursor-pointer text-[11px] font-semibold uppercase tracking-wider text-zinc-500 hover:text-zinc-300">
                      Delivery · {formatPlatformMode(target.mode)} · {target.daily_cap}/day
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
                        {(target.enabled ?? true) ? "Disable" : "Enable"}
                      </button>
                    </div>
                    {(recovery || latest) && (
                      <p className="mt-3 text-[11px] leading-relaxed text-zinc-500">
                        {recovery || `Last: ${cleanPublishStatus(latest?.status)}`}
                      </p>
                    )}
                  </details>
                ) : null}

                {!unavailable && latestRecovery ? (
                  <div className="mt-4 flex flex-wrap items-center gap-2 rounded-2xl border border-danger/[0.20] bg-danger/[0.05] p-3">
                    <p className="min-w-0 flex-1 text-[11px] leading-relaxed text-danger/90">{recovery}</p>
                    {latestRecovery.kind === "reconnect" && supportsOauth ? (
                      <RecoveryAction label={latestRecovery.label} disabled={isBusy} onClick={() => onStartOauth(target.platform)} />
                    ) : latestRecovery.kind === "rerender" ? (
                      <RecoveryAction label="Open Review" href="/?section=review" />
                    ) : latestRecovery.kind === "retry" && ready ? (
                      <RecoveryAction label="Test connection" disabled={isBusy} onClick={() => onTestConnection(target.platform)} />
                    ) : null}
                  </div>
                ) : null}

                {unavailable && target.platform === "tiktok" && onDisconnect ? (
                  (credentials?.vault?.secret_keys || []).some((key) => key.startsWith("TIKTOK_")) ? (
                    <button
                      type="button"
                      disabled={isBusy}
                      onClick={() => onDisconnect(target.platform)}
                      className="mt-4 inline-flex h-10 w-full items-center justify-center rounded-full border border-amber-500/30 bg-amber-500/10 px-4 text-xs font-bold uppercase tracking-wider text-amber-200 hover:bg-amber-500/20 disabled:opacity-50"
                    >
                      Clear stale credentials
                    </button>
                  ) : null
                ) : null}

                <div className="mt-4 flex items-center gap-2">
                  {!unavailable && showPostizMap ? (
                    <button
                      type="button"
                      disabled={isBusy}
                      onClick={() => void openMap(target.platform)}
                      className="inline-flex h-11 flex-1 items-center justify-center gap-1.5 rounded-full bg-cyan px-4 text-xs font-bold uppercase tracking-wider text-ink shadow-[0_8px_24px_rgba(102,232,249,0.18)] transition-all hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      Map Postiz channel
                    </button>
                  ) : null}
                  {!unavailable && (supportsOauth || isTelegram) && !ready && !showPostizMap ? (
                    <button
                      type="button"
                      disabled={isBusy || (isTelegram && !onSaveCredentials)}
                      onClick={() => {
                        if (isTelegram) {
                          setTelegramDialogOpen(true);
                          return;
                        }
                        onStartOauth(target.platform);
                      }}
                      className="inline-flex h-11 flex-1 items-center justify-center gap-1.5 rounded-full bg-cyan px-4 text-xs font-bold uppercase tracking-wider text-ink shadow-[0_8px_24px_rgba(102,232,249,0.18)] transition-all hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      {connectRunning || (isTelegram && telegramSaving) ? (
                        <>
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          <span>Connecting…</span>
                        </>
                      ) : (
                        <span>Connect account</span>
                      )}
                    </button>
                  ) : null}

                  {!unavailable && ready ? (
                    <button
                      type="button"
                      disabled={isBusy}
                      onClick={() => onTestConnection(target.platform)}
                      className="inline-flex h-10 flex-1 items-center justify-center gap-1.5 rounded-full border border-white/[0.10] bg-black/20 text-xs font-bold uppercase tracking-wider text-zinc-200 transition-all hover:border-cyan/[0.30] hover:text-cyan disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      {testRunning ? (
                        <>
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          <span>Testing…</span>
                        </>
                      ) : (
                        <>
                          <Wifi className="h-3.5 w-3.5" />
                          <span>Test</span>
                        </>
                      )}
                    </button>
                  ) : null}

                  {!unavailable && (ready || supportsOauth || isTelegram || postizConnected) && (
                    <PlatformActionMenu
                      disabled={isBusy}
                      ready={ready}
                      supportsOauth={supportsOauth}
                      platform={target.platform}
                      onTestConnection={onTestConnection}
                      onStartOauth={onStartOauth}
                      onDisconnect={onDisconnect}
                      onMapPostiz={postizConnected && onMapPostiz ? () => void openMap(target.platform) : undefined}
                    />
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="rounded-[32px] border border-white/[0.08] bg-surface/30 p-6 backdrop-blur-md xl:self-start">
        <h3 className="text-lg font-semibold text-white tracking-[-0.02em]">
          Publish <span className="font-editorial italic font-normal text-cyan">logs</span>
        </h3>
        <p className="mt-1.5 text-xs text-zinc-400 leading-relaxed">
          Recent connection tests and scheduled publishes for this workspace.
        </p>

        <div className="mt-5 grid gap-2.5">
          {recentLogs.length ? (
            recentLogs.map((attempt) => (
              <div key={attempt.id} className="rounded-2xl border border-white/[0.04] bg-black/15 p-3.5">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-xs font-bold text-white">{platformLabel(attempt.platform)}</p>
                  <span className={`rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${statusTone(attempt.status)}`}>
                    {cleanPublishStatus(attempt.status)}
                  </span>
                </div>
                {attempt.error ? <p className="mt-2 text-[11px] leading-relaxed text-danger/80">{publishActionHint(attempt.error)}</p> : null}
              </div>
            ))
          ) : (
            <EmptyState title="No activity yet" text="Logs appear after you connect an account or a scheduled post goes out." />
          )}
        </div>
      </div>

      {onSaveCredentials ? (
        <TelegramConnectDialog
          open={telegramDialogOpen}
          saving={telegramSaving}
          onClose={() => setTelegramDialogOpen(false)}
          onSave={(values) => onSaveCredentials("telegram_channel", values)}
        />
      ) : null}
      {onConnectPostiz ? (
        <PostizConnectDialog
          open={postizDialogOpen}
          saving={postizSaving}
          defaultUrl={postizOrigin}
          onClose={() => setPostizDialogOpen(false)}
          onSave={onConnectPostiz}
        />
      ) : null}
      {onMapPostiz && mapPlatform ? (
        <PostizMapDialog
          open={Boolean(mapPlatform)}
          platform={mapPlatform}
          saving={actionStates[`postiz-map:${mapPlatform}`]?.status === "running"}
          integrations={mapIntegrations}
          loading={mapLoading}
          onClose={() => setMapPlatform("")}
          onSave={(integration) => onMapPostiz(mapPlatform, integration)}
        />
      ) : null}

    </div>
      ) : null}
    </section>
  );
}
