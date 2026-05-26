import type {
  BrandTemplate,
  DurationPreset,
  EngineHealth,
  GenerationJob,
  GenreOption,
  HyperframesCatalog,
  HyperframesTemplate,
} from "@/lib/media-api";

export type {BrandTemplate, DurationPreset, EngineHealth, GenerationJob, GenreOption, HyperframesCatalog, HyperframesTemplate};

export type ActionUiState = {status: "running" | "done" | "failed"; message: string};
