/** Operator publish destinations (keep in sync with media_engine/publish_platforms.py). */

export const disabledPublishPlatforms: Record<string, string> = {
  tiktok:
    "TikTok rejected personal/internal developer apps for production posting. Use the TikTok app manually until a vendor-approved API channel is available.",
};

export const publishDestinationPlatforms = [
  "telegram_channel",
  "youtube_shorts",
  "youtube_video",
  "facebook_reels",
  "tiktok",
] as const;

export type PublishDestinationPlatform = (typeof publishDestinationPlatforms)[number];

/** Platforms that can be scheduled or published from Otonom. */
export const publishPlatforms = [
  "telegram_channel",
  "youtube_shorts",
  "youtube_video",
  "facebook_reels",
] as const;

export type PublishPlatform = (typeof publishPlatforms)[number];

export function isPublishPlatformDisabled(platform: string): boolean {
  return platform in disabledPublishPlatforms;
}

export function disabledPublishPlatformReason(platform: string): string {
  return disabledPublishPlatforms[platform] ?? "This destination is temporarily unavailable.";
}

export const oauthPlatforms = new Set<string>(["youtube_shorts", "youtube_video", "facebook_reels"]);
