import type {
  AngleRecommendation,
  BrandTemplate,
  DurationPreset,
  EngineHealth,
  GenerationJob,
  GenreOption,
  HyperframesCatalog,
  HyperframesTemplate,
  ShortlistCandidate,
} from "@/lib/media-api";

export type {
  AngleRecommendation,
  BrandTemplate,
  DurationPreset,
  EngineHealth,
  GenerationJob,
  GenreOption,
  HyperframesCatalog,
  HyperframesTemplate,
  ShortlistCandidate,
};

export type ActionUiState = {status: "running" | "done" | "failed"; message: string};
