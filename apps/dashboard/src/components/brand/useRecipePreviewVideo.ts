"use client";

import {useEffect, useState} from "react";
import {fetchHyperframesPreviewStatus, prewarmHyperframesTemplatePreview, type HyperframesTemplate} from "@/lib/media-api";

export type RecipePreviewFormat = "short_9_16" | "long_16_9";

export function useRecipePreviewVideo(
  template: HyperframesTemplate | null | undefined,
  format: RecipePreviewFormat,
) {
  const templateId = template?.id ?? "";
  const hasInstantVideo = Boolean(template?.preview_video_urls?.[format]);
  const apiPreviewUrl = template?.preview_urls?.[format];
  const initiallyCached = hasInstantVideo || Boolean(template?.preview_cache_ready?.[format]);

  const [cacheReady, setCacheReady] = useState(initiallyCached);
  const [generatingPreview, setGeneratingPreview] = useState(false);
  const [previewUnavailable, setPreviewUnavailable] = useState(false);
  const [videoLoaded, setVideoLoaded] = useState(false);
  const [videoError, setVideoError] = useState(false);

  const previewUrl = template?.preview_video_urls?.[format] || (cacheReady ? apiPreviewUrl : undefined);
  const showVideo = Boolean(previewUrl && !videoError);

  useEffect(() => {
    setCacheReady(initiallyCached);
    setVideoLoaded(false);
    setVideoError(false);
    setPreviewUnavailable(false);
  }, [templateId, format, initiallyCached]);

  useEffect(() => {
    if (!templateId || cacheReady || hasInstantVideo || previewUnavailable) return;
    let cancelled = false;

    async function warmPreview() {
      setGeneratingPreview(true);
      try {
        const status = await fetchHyperframesPreviewStatus(templateId, format);
        if (cancelled) return;
        if (status.ready) {
          setCacheReady(true);
          return;
        }
        if (status.renderer_ready === false) {
          setPreviewUnavailable(true);
          return;
        }
        if (!apiPreviewUrl) {
          setPreviewUnavailable(true);
          return;
        }
        void prewarmHyperframesTemplatePreview(templateId, templateId.startsWith("brand:")).catch(() => undefined);
        for (let attempt = 0; attempt < 45 && !cancelled; attempt += 1) {
          await new Promise((resolve) => window.setTimeout(resolve, 2000));
          const next = await fetchHyperframesPreviewStatus(templateId, format);
          if (cancelled) return;
          if (next.ready) {
            setCacheReady(true);
            return;
          }
          if (next.renderer_ready === false) {
            setPreviewUnavailable(true);
            return;
          }
        }
        if (!cancelled) setPreviewUnavailable(true);
      } finally {
        if (!cancelled) setGeneratingPreview(false);
      }
    }

    void warmPreview();
    return () => {
      cancelled = true;
    };
  }, [apiPreviewUrl, cacheReady, format, hasInstantVideo, previewUnavailable, templateId]);

  return {
    previewUrl,
    showVideo,
    generatingPreview,
    previewUnavailable,
    videoLoaded,
    videoError,
    setVideoLoaded,
    setVideoError,
  };
}
