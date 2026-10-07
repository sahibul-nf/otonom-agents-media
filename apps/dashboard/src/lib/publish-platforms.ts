/** Operator publish destinations (keep in sync with media_engine/publish_platforms.py). */

export const disabledPublishPlatforms: Record<string, string> = {
  tiktok:
    "Native TikTok OAuth is not supported (developer app removed). Post manually in the TikTok app, or map TikTok in Postiz when that connector is available.",
};

export type PublishDestinationPlatform =
  | "telegram_channel"
  | "youtube_shorts"
  | "youtube_video"
  | "facebook_reels"
  | "instagram"
  | "tiktok";

export const publishDestinationPlatforms: string[] = [
  "telegram_channel",
  "youtube_shorts",
  "youtube_video",
  "facebook_reels",
  "instagram",
  "tiktok",
];

/** Platforms that can be scheduled or published from Otonom. */
export type PublishPlatform = "telegram_channel" | "youtube_shorts" | "youtube_video" | "facebook_reels";

export const publishPlatforms: string[] = [
  "telegram_channel",
  "youtube_shorts",
  "youtube_video",
  "facebook_reels",
];

export function isPublishPlatformDisabled(platform: string): boolean {
  return platform in disabledPublishPlatforms;
}

export function disabledPublishPlatformReason(platform: string): string {
  return disabledPublishPlatforms[platform] ?? "This destination is temporarily unavailable.";
}

export const oauthPlatforms = new Set<string>(["youtube_shorts", "youtube_video", "facebook_reels"]);
