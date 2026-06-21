export type RecipeTheme = {
  accent: string;
  secondary: string;
  caption: string;
  caption2: string;
  hook: string;
  body: string;
  cta: string;
  fontFamily: string;
  captionStyle: string;
  motionPreset: string;
  colorGrade: string;
};

export type RecipeOverlayProps = {
  templateId: string;
  theme: RecipeTheme;
  compact?: boolean;
};
