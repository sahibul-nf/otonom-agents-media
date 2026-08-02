"use client";

import {FocusModal} from "@/components/FocusModal";
import {SlideToConfirm} from "@/components/shared/SlideToConfirm";
import {type MediaProfile, apiPost} from "@/lib/media-api";
import {Loader2, Pencil, Plus, Trash2} from "lucide-react";
import {useEffect, useMemo, useState} from "react";

function slugify(value: string) {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9._\s-]/g, "")
    .replace(/[\s.]+/g, "_")
    .replace(/_+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 40);
}

type WorkspaceManagerModalProps = {
  open: boolean;
  profiles: MediaProfile[];
  activeProfileId: string;
  onClose: () => void;
  onProfilesChange: (profiles: MediaProfile[]) => void;
  onSwitchProfile: (profileId: string) => void;
  onStatus: (message: string) => void;
};

export function WorkspaceManagerModal({
  open,
  profiles,
  activeProfileId,
  onClose,
  onProfilesChange,
  onSwitchProfile,
  onStatus,
}: WorkspaceManagerModalProps) {
  const [mode, setMode] = useState<"list" | "create" | "edit" | "delete">("list");
  const [selectedId, setSelectedId] = useState(activeProfileId);
  const [name, setName] = useState("");
  const [id, setId] = useState("");
  const [idTouched, setIdTouched] = useState(false);
  const [niche, setNiche] = useState("");
  const [ctaText, setCtaText] = useState("");
  const [watermarkText, setWatermarkText] = useState("");
  const [forceDelete, setForceDelete] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [usageHint, setUsageHint] = useState("");

  const selected = useMemo(
    () => profiles.find((profile) => profile.id === selectedId) || null,
    [profiles, selectedId],
  );

  useEffect(() => {
    if (!open) return;
    setMode("list");
    setSelectedId(activeProfileId);
    setError("");
    setUsageHint("");
    setForceDelete(false);
    setBusy(false);
  }, [open, activeProfileId]);

  function startCreate() {
    setMode("create");
    setName("");
    setId("");
    setIdTouched(false);
    setNiche("General short-form clips");
    setCtaText("");
    setWatermarkText("");
    setError("");
  }

  function startEdit(profile: MediaProfile) {
    setMode("edit");
    setSelectedId(profile.id);
    setName(profile.name || profile.id);
    setId(profile.id);
    setNiche(profile.niche || "");
    setCtaText(profile.cta_text || "");
    setWatermarkText(profile.watermark_text || "");
    setError("");
  }

  function startDelete(profile: MediaProfile) {
    setMode("delete");
    setSelectedId(profile.id);
    setForceDelete(false);
    setError("");
    setUsageHint("");
  }

  async function submitCreate() {
    setBusy(true);
    setError("");
    try {
      const result = await apiPost<{profile: MediaProfile; profiles: MediaProfile[]}>("profiles", {
        id: id.trim() || slugify(name),
        name: name.trim(),
        niche: niche.trim(),
        cta_text: ctaText.trim(),
        watermark_text: watermarkText.trim(),
      });
      onProfilesChange(result.profiles || []);
      onSwitchProfile(result.profile.id);
      onStatus(`Workspace “${result.profile.name}” created`);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create failed");
    } finally {
      setBusy(false);
    }
  }

  async function submitUpdate() {
    if (!selected) return;
    setBusy(true);
    setError("");
    try {
      const result = await apiPost<{profile: MediaProfile; profiles: MediaProfile[]}>("profile-update", {
        id: selected.id,
        name: name.trim(),
        niche: niche.trim(),
        cta_text: ctaText.trim(),
        watermark_text: watermarkText.trim(),
      });
      onProfilesChange(result.profiles || []);
      onStatus(`Workspace “${result.profile.name}” updated`);
      setMode("list");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update failed");
    } finally {
      setBusy(false);
    }
  }

  async function submitDelete() {
    if (!selected) return;
    setBusy(true);
    setError("");
    setUsageHint("");
    try {
      const result = await apiPost<{profiles: MediaProfile[]; deleted: boolean}>("profile-delete", {
        id: selected.id,
        confirm: selected.id,
        force: forceDelete,
      });
      const nextProfiles = result.profiles || [];
      onProfilesChange(nextProfiles);
      if (activeProfileId === selected.id) {
        const fallback = nextProfiles.find((profile) => profile.id === "nourbit") || nextProfiles[0];
        if (fallback) onSwitchProfile(fallback.id);
      }
      onStatus(`Workspace “${selected.name || selected.id}” deleted`);
      onClose();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Delete failed";
      setError(message);
      if (/force=true|still has/i.test(message)) {
        setUsageHint("Turn on force delete to remove clips, schedule, watch channels, and sources for this workspace.");
        setForceDelete(true);
      }
    } finally {
      setBusy(false);
    }
  }

  const subtitle =
    mode === "create"
      ? "Create a new scoped workspace for clips, channels, and publish credentials."
      : mode === "edit"
        ? "Rename the display name. The internal name stays the same."
        : mode === "delete"
          ? "Built-in workspaces stay protected. Custom workspaces need an explicit confirm."
          : "Add, rename, or remove workspaces from the dashboard.";

  return (
    <FocusModal open={open} title="Manage workspaces" subtitle={subtitle} width="default" onClose={onClose}>
      <div className="space-y-5 p-5">
        {mode === "list" ? (
          <>
            <div className="flex justify-end">
              <button
                type="button"
                onClick={startCreate}
                className="inline-flex h-10 items-center gap-2 rounded-full bg-cyan px-4 text-sm font-semibold text-ink"
              >
                <Plus className="h-4 w-4" /> New workspace
              </button>
            </div>
            <ul className="divide-y divide-white/[0.06] overflow-hidden rounded-2xl border border-white/[0.08]">
              {profiles.map((profile) => (
                <li key={profile.id} className="flex items-center gap-3 bg-surface-raised/40 px-4 py-3">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-semibold text-white">
                      {profile.name || profile.id}
                      {profile.id === activeProfileId ? (
                        <span className="ml-2 text-[10px] font-bold uppercase tracking-wider text-cyan">Active</span>
                      ) : null}
                    </p>
                    <p className="truncate text-xs text-zinc-500">
                      {profile.id}
                      {profile.protected ? " · built-in" : ""}
                      {profile.niche ? ` · ${profile.niche}` : ""}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => onSwitchProfile(profile.id)}
                    className="rounded-full border border-white/[0.10] px-3 py-1.5 text-xs font-medium text-zinc-300 hover:bg-white/[0.04]"
                  >
                    Switch
                  </button>
                  <button
                    type="button"
                    aria-label={`Edit ${profile.name || profile.id}`}
                    onClick={() => startEdit(profile)}
                    className="rounded-full border border-white/[0.10] p-2 text-zinc-300 hover:bg-white/[0.04]"
                  >
                    <Pencil className="h-3.5 w-3.5" />
                  </button>
                  <button
                    type="button"
                    aria-label={`Delete ${profile.name || profile.id}`}
                    disabled={Boolean(profile.protected)}
                    onClick={() => startDelete(profile)}
                    className="rounded-full border border-white/[0.10] p-2 text-zinc-300 hover:bg-white/[0.04] disabled:cursor-not-allowed disabled:opacity-30"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </li>
              ))}
            </ul>
          </>
        ) : null}

        {mode === "create" || mode === "edit" ? (
          <div className="space-y-4">
            <label className="block space-y-1.5">
              <span className="text-[11px] font-bold uppercase tracking-wider text-zinc-500">Display name</span>
              <input
                data-autofocus
                value={name}
                onChange={(event) => {
                  const next = event.target.value;
                  setName(next);
                  if (mode === "create" && !idTouched) setId(slugify(next));
                }}
                className="h-11 w-full rounded-xl border border-white/[0.10] bg-canvas-deep px-3 text-sm text-white outline-none focus:border-cyan/40"
                placeholder="Acme Clips"
              />
            </label>
            <label className="block space-y-1.5">
              <span className="text-[11px] font-bold uppercase tracking-wider text-zinc-500">Internal name</span>
              <input
                value={id}
                disabled={mode === "edit"}
                onChange={(event) => {
                  setIdTouched(true);
                  setId(slugify(event.target.value));
                }}
                className="h-11 w-full rounded-xl border border-white/[0.10] bg-canvas-deep px-3 text-sm text-white outline-none focus:border-cyan/40 disabled:opacity-60"
                placeholder="acme_clips"
              />
              <span className="text-xs text-zinc-500">
                {mode === "edit" ? "Can’t change after create." : "Auto-filled from the display name. Used behind the scenes."}
              </span>
            </label>
            <label className="block space-y-1.5">
              <span className="text-[11px] font-bold uppercase tracking-wider text-zinc-500">Niche</span>
              <input
                value={niche}
                onChange={(event) => setNiche(event.target.value)}
                className="h-11 w-full rounded-xl border border-white/[0.10] bg-canvas-deep px-3 text-sm text-white outline-none focus:border-cyan/40"
              />
            </label>
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="block space-y-1.5">
                <span className="text-[11px] font-bold uppercase tracking-wider text-zinc-500">CTA text</span>
                <input
                  value={ctaText}
                  onChange={(event) => setCtaText(event.target.value)}
                  className="h-11 w-full rounded-xl border border-white/[0.10] bg-canvas-deep px-3 text-sm text-white outline-none focus:border-cyan/40"
                />
              </label>
              <label className="block space-y-1.5">
                <span className="text-[11px] font-bold uppercase tracking-wider text-zinc-500">Watermark</span>
                <input
                  value={watermarkText}
                  onChange={(event) => setWatermarkText(event.target.value)}
                  className="h-11 w-full rounded-xl border border-white/[0.10] bg-canvas-deep px-3 text-sm text-white outline-none focus:border-cyan/40"
                />
              </label>
            </div>
            {error ? <p className="text-sm text-rose-300">{error}</p> : null}
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => setMode("list")}
                className="h-11 rounded-full border border-white/[0.10] px-4 text-sm font-medium text-zinc-200"
              >
                Back
              </button>
              <button
                type="button"
                disabled={busy || !name.trim() || (mode === "create" && !id.trim())}
                onClick={() => void (mode === "create" ? submitCreate() : submitUpdate())}
                className="inline-flex h-11 items-center gap-2 rounded-full bg-cyan px-4 text-sm font-semibold text-ink disabled:opacity-40"
              >
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                {mode === "create" ? "Create workspace" : "Save changes"}
              </button>
            </div>
          </div>
        ) : null}

        {mode === "delete" && selected ? (
          <div className="space-y-4">
            <p className="text-sm leading-6 text-zinc-300">
              Delete <span className="font-semibold text-white">{selected.name || selected.id}</span> ({selected.id})?
              This removes its credential vault. Related clips/schedule/channels are kept unless you force delete.
            </p>
            <label className="flex items-start gap-3 rounded-xl border border-white/[0.08] bg-canvas-deep/60 px-3 py-3 text-sm text-zinc-300">
              <input
                type="checkbox"
                checked={forceDelete}
                onChange={(event) => setForceDelete(event.target.checked)}
                className="mt-1"
              />
              <span>Force delete related clips, schedule rows, watch channels, and sources for this workspace.</span>
            </label>
            {usageHint ? <p className="text-sm text-amber-200">{usageHint}</p> : null}
            {error ? <p className="text-sm text-rose-300">{error}</p> : null}
            <SlideToConfirm
              label={`Slide to delete ${selected.id}`}
              activeLabel="Release to delete..."
              disabled={busy || Boolean(selected.protected)}
              isLoading={busy}
              onConfirm={() => void submitDelete()}
            />
            <button
              type="button"
              onClick={() => setMode("list")}
              className="h-11 rounded-full border border-white/[0.10] px-4 text-sm font-medium text-zinc-200"
            >
              Back
            </button>
          </div>
        ) : null}
      </div>
    </FocusModal>
  );
}
