"use client";

import {ChevronDown, Settings2} from "lucide-react";

type ProfileOption = {
  id: string;
  name?: string;
};

type WorkspaceSwitcherProps = {
  profiles: ProfileOption[];
  profileId: string;
  onSwitch: (profileId: string) => void;
  onManage: () => void;
  variant?: "sidebar" | "mobile";
};

function workspaceInitials(label: string) {
  const parts = label.trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return "W";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0] || ""}${parts[1][0] || ""}`.toUpperCase();
}

export function WorkspaceSwitcher({
  profiles,
  profileId,
  onSwitch,
  onManage,
  variant = "sidebar",
}: WorkspaceSwitcherProps) {
  const options = profiles.length ? profiles : [{id: profileId, name: profileId}];
  const active = options.find((profile) => profile.id === profileId) || options[0];
  const activeLabel = active?.name || active?.id || profileId;
  const initials = workspaceInitials(activeLabel);

  if (variant === "mobile") {
    return (
      <div className="flex items-center gap-2">
        <div className="relative min-w-0 flex-1">
          <span className="pointer-events-none absolute left-2.5 top-1/2 grid h-6 w-6 -translate-y-1/2 place-items-center rounded-full bg-cyan/[0.12] text-[9px] font-bold text-cyan">
            {initials}
          </span>
          <select
            value={profileId}
            onChange={(event) => onSwitch(event.target.value)}
            className="h-9 w-full appearance-none truncate rounded-full border border-white/[0.1] bg-surface py-0 pl-10 pr-8 text-xs font-semibold text-zinc-100 outline-none focus:border-cyan/35"
            aria-label={`Workspace: ${activeLabel}`}
          >
            {options.map((profile) => (
              <option key={profile.id} value={profile.id}>
                {profile.name || profile.id}
              </option>
            ))}
          </select>
          <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-zinc-500" />
        </div>
        <button
          type="button"
          onClick={onManage}
          className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-white/[0.1] bg-surface text-zinc-400 transition hover:border-cyan/30 hover:text-cyan"
          aria-label="Manage workspaces"
          title="Manage workspaces"
        >
          <Settings2 className="h-3.5 w-3.5" />
        </button>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-white/[0.07] bg-gradient-to-b from-white/[0.04] to-black/20 p-2.5 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
      <div className="mb-2 flex items-center justify-between gap-2 px-1">
        <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-zinc-500">Workspace</p>
        <button
          type="button"
          onClick={onManage}
          className="inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[11px] font-semibold text-zinc-500 transition hover:bg-white/[0.04] hover:text-cyan"
        >
          <Settings2 className="h-3 w-3" />
          Manage
        </button>
      </div>

      <div className="relative">
        <span className="pointer-events-none absolute left-2.5 top-1/2 grid h-7 w-7 -translate-y-1/2 place-items-center rounded-full border border-cyan/25 bg-cyan/[0.1] text-[10px] font-bold tracking-wide text-cyan">
          {initials}
        </span>
        <select
          value={profileId}
          onChange={(event) => onSwitch(event.target.value)}
          className="h-11 w-full cursor-pointer appearance-none truncate rounded-xl border border-white/[0.08] bg-black/35 py-0 pl-11 pr-9 text-[13px] font-semibold text-white outline-none transition hover:border-white/[0.14] focus:border-cyan/40 focus:bg-black/45"
          aria-label={`Workspace: ${activeLabel}`}
        >
          {options.map((profile) => (
            <option key={profile.id} value={profile.id} className="bg-[#17171a] text-white">
              {profile.name || profile.id}
            </option>
          ))}
        </select>
        <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
      </div>
    </div>
  );
}
