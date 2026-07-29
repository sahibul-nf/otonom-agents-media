"use client";

import {Loader2, Pause, Play, Plus, Radio, RefreshCcw, Trash2} from "lucide-react";
import {useState, type ReactNode} from "react";
import type {WatchChannel} from "@/lib/media-api";

type ActionUiState = {status: "running" | "done" | "failed"; message: string};

type Props = {
  channels: WatchChannel[];
  profileId: string;
  actionStates: Record<string, ActionUiState>;
  onAdd: (channelUrl: string, label: string) => Promise<void> | void;
  onToggle: (channel: WatchChannel, enabled: boolean) => Promise<void> | void;
  onPoll: (channel: WatchChannel) => Promise<void> | void;
  onDelete: (channel: WatchChannel) => Promise<void> | void;
  renderActionStatus: (state?: ActionUiState) => ReactNode;
};

function formatStamp(value?: string) {
  if (!value) return "Never";
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

export function WatchChannelsSection({
  channels,
  profileId,
  actionStates,
  onAdd,
  onToggle,
  onPoll,
  onDelete,
  renderActionStatus,
}: Props) {
  const [url, setUrl] = useState("");
  const [label, setLabel] = useState("");

  return (
    <section className="rounded-[28px] border border-white/[0.07] bg-surface/30 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-widest text-cyan">Watch YouTube sources</p>
          <h3 className="mt-1 text-lg font-semibold text-white">Auto-clip new uploads</h3>
          <p className="mt-1 max-w-2xl text-sm text-zinc-500">
            Workspace <span className="font-semibold text-zinc-300">{profileId}</span> polls a YouTube channel for new videos and enqueues clip jobs. This is not where you connect Facebook/TikTok publish accounts — use Publish accounts for that.
          </p>
        </div>
      </div>

      <form
        className="mt-5 grid gap-3 md:grid-cols-[1fr_180px_auto]"
        onSubmit={(event) => {
          event.preventDefault();
          void (async () => {
            await onAdd(url, label);
            setUrl("");
            setLabel("");
          })();
        }}
      >
        <input
          value={url}
          onChange={(event) => setUrl(event.target.value)}
          placeholder="https://www.youtube.com/@channel"
          className="h-11 rounded-2xl border border-white/[0.08] bg-black/30 px-4 text-sm text-white outline-none placeholder:text-zinc-600 focus:border-cyan/40"
          required
        />
        <input
          value={label}
          onChange={(event) => setLabel(event.target.value)}
          placeholder="Label (optional)"
          className="h-11 rounded-2xl border border-white/[0.08] bg-black/30 px-4 text-sm text-white outline-none placeholder:text-zinc-600 focus:border-cyan/40"
        />
        <button
          type="submit"
          disabled={Boolean(actionStates["watch:add"]?.status === "running")}
          className="inline-flex h-11 items-center justify-center gap-2 rounded-full bg-cyan px-5 text-sm font-semibold text-ink disabled:opacity-60"
        >
          {actionStates["watch:add"]?.status === "running" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
          Add YouTube source
        </button>
      </form>
      {renderActionStatus(actionStates["watch:add"])}

      <div className="mt-5 grid gap-3">
        {channels.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-white/[0.08] bg-black/20 px-4 py-8 text-center text-sm text-zinc-500">
            No watched YouTube sources yet. Paste a channel URL to start auto-clipping new uploads.
          </div>
        ) : (
          channels.map((channel) => {
            const busy =
              actionStates[`watch:${channel.id}:poll`]?.status === "running" ||
              actionStates[`watch:${channel.id}:toggle`]?.status === "running" ||
              actionStates[`watch:${channel.id}:delete`]?.status === "running";
            return (
              <article key={channel.id} className="rounded-2xl border border-white/[0.07] bg-black/20 p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <Radio className={`h-4 w-4 ${channel.enabled ? "text-cyan" : "text-zinc-600"}`} />
                      <h4 className="truncate text-sm font-semibold text-white">{channel.label || channel.channel_url}</h4>
                      <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${channel.enabled ? "bg-cyan/10 text-cyan" : "bg-white/5 text-zinc-500"}`}>
                        {channel.enabled ? "Watching" : "Paused"}
                      </span>
                    </div>
                    <p className="mt-1 truncate text-xs text-zinc-500">{channel.channel_url}</p>
                    <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-zinc-500">
                      <span>Last poll: {formatStamp(channel.last_polled_at)}</span>
                      <span>Last new: {channel.last_new_video_id || "—"}</span>
                      <span>Last job: {channel.last_clip_job_id || "—"}</span>
                      <span>Permission: {channel.permission_status}</span>
                    </div>
                    {channel.last_error ? <p className="mt-2 text-xs text-danger">{channel.last_error}</p> : null}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void onToggle(channel, !channel.enabled)}
                      className="inline-flex h-9 items-center gap-1.5 rounded-full border border-white/[0.08] px-3 text-xs font-semibold text-zinc-300 hover:border-cyan/30 hover:text-cyan disabled:opacity-50"
                    >
                      {channel.enabled ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
                      {channel.enabled ? "Pause" : "Resume"}
                    </button>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void onPoll(channel)}
                      className="inline-flex h-9 items-center gap-1.5 rounded-full border border-white/[0.08] px-3 text-xs font-semibold text-zinc-300 hover:border-cyan/30 hover:text-cyan disabled:opacity-50"
                    >
                      <RefreshCcw className="h-3.5 w-3.5" /> Poll now
                    </button>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void onDelete(channel)}
                      className="inline-flex h-9 items-center gap-1.5 rounded-full border border-danger/20 px-3 text-xs font-semibold text-danger hover:bg-danger/10 disabled:opacity-50"
                    >
                      <Trash2 className="h-3.5 w-3.5" /> Remove
                    </button>
                  </div>
                </div>
                {renderActionStatus(actionStates[`watch:${channel.id}:poll`] || actionStates[`watch:${channel.id}:toggle`] || actionStates[`watch:${channel.id}:delete`])}
              </article>
            );
          })
        )}
      </div>
    </section>
  );
}
