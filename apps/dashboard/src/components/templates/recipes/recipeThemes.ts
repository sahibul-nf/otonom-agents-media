import type {RecipeTheme} from "./types";

const base = (partial: Partial<RecipeTheme> & Pick<RecipeTheme, "accent" | "secondary" | "caption" | "caption2">): RecipeTheme => ({
  fontFamily: "Inter, sans-serif",
  captionStyle: "Weighted captions",
  motionPreset: "fade-pop",
  colorGrade: "neutral grade",
  ...partial,
  hook: partial.hook ?? partial.caption,
  body: partial.body ?? "",
  cta: partial.cta ?? "",
});

export const recipeThemes: Record<string, RecipeTheme> = {
  spiritual_reflective: base({accent: "#d8b45f", secondary: "#8ee6c8", caption: "Allah selalu bersama", caption2: "bahkan saat hati merasa jauh", fontFamily: "Lora, serif", captionStyle: "Editorial serif underline", motionPreset: "soft-vignette-fade", colorGrade: "warm cream grade"}),
  energy_warm_question: base({accent: "#ffe566", secondary: "#ff7ad1", caption: "more views?", caption2: "ask the real question", fontFamily: "Caveat, cursive", captionStyle: "Yellow sticky note", motionPreset: "note-pop", colorGrade: "warm social"}),
  arion_pink_callout: base({accent: "#ff7ad1", secondary: "#f8fafc", caption: "say it louder", caption2: "center callout energy", fontFamily: "Rubik, sans-serif", captionStyle: "Pink callout", motionPreset: "callout-bounce", colorGrade: "pink pop"}),
  quintessence_serif: base({accent: "#e8c77d", secondary: "#f8fafc", caption: "More clarity", caption2: "with serif emphasis", fontFamily: "DM Serif Display, serif", captionStyle: "Display serif", motionPreset: "serif-fade", colorGrade: "editorial cream"}),
  archive_magazine: base({accent: "#d8b45f", secondary: "#8ee6c8", caption: "Guidelines", caption2: "editorial archive", fontFamily: "Playfair Display, serif", captionStyle: "Magazine cover", motionPreset: "cover-slide", colorGrade: "magazine muted"}),
  story_handwritten: base({accent: "#ff9f68", secondary: "#fef08a", caption: "Creative", caption2: "handwritten accent", fontFamily: "Caveat, cursive", captionStyle: "Handwritten accent", motionPreset: "scribble-in", colorGrade: "story warm"}),
  kai_mustard_uppercase: base({accent: "#d4a017", secondary: "#111111", caption: "MUSTARD MODE", caption2: "ALL CAPS IMPACT", fontFamily: "Oswald, sans-serif", captionStyle: "Mustard card", motionPreset: "card-slam", colorGrade: "mustard punch"}),
  byline_trust_quote: base({accent: "#f8fafc", secondary: "#7dd3fc", caption: "Trust the process", caption2: "quote-led narrative", fontFamily: "Libre Baskerville, serif", captionStyle: "Centered quote", motionPreset: "quote-fade", colorGrade: "trust neutral"}),
  sonnet_botanical: base({accent: "#9fe7c4", secondary: "#f8d35c", caption: "lessons", caption2: "soft botanical mood", fontFamily: "Fraunces, serif", captionStyle: "Script botanical", motionPreset: "botanical-drift", colorGrade: "soft botanical"}),
  rocket_glitch: base({accent: "#f0abfc", secondary: "#22d3ee", caption: "LEVEL UP", caption2: "VHS glitch energy", fontFamily: "Bebas Neue, sans-serif", captionStyle: "VHS glitch", motionPreset: "vhs-glitch", colorGrade: "retro glitch"}),
  grit_training_stamp: base({accent: "#22c55e", secondary: "#111111", caption: "TRAINING", caption2: "dark grit mood", fontFamily: "Archivo Black, sans-serif", captionStyle: "Training stamp", motionPreset: "stamp-slam", colorGrade: "dark grit"}),
  cove_callout_pill: base({accent: "#ff7ad1", secondary: "#67e8f9", caption: "add captions", caption2: "in seconds", fontFamily: "Outfit, sans-serif", captionStyle: "Pill stack", motionPreset: "pill-stack-rise", colorGrade: "cove bright"}),
  pulse_remember_overlay: base({accent: "#dc2626", secondary: "#f8fafc", caption: "REMEMBER", caption2: "THE CONSISTENCY", fontFamily: "Oswald, sans-serif", captionStyle: "Red banner", motionPreset: "banner-punch", colorGrade: "urgent red"}),
  neon_seize_future: base({accent: "#ff2a85", secondary: "#00f3ff", caption: "SEIZE THE FUTURE", caption2: "neon star burst", fontFamily: "Syne, sans-serif", captionStyle: "Neon burst", motionPreset: "star-burst", colorGrade: "neon burst"}),
  velocity_business_promo: base({accent: "#facc15", secondary: "#f8fafc", caption: "BOOST", caption2: "YOUR BUSINESS", fontFamily: "Archivo Black, sans-serif", captionStyle: "Yellow stack", motionPreset: "stack-rise", colorGrade: "velocity yellow"}),
  blueprint_grid_paper: base({accent: "#7dd3fc", secondary: "#bae6fd", caption: "how to build", caption2: "anything", fontFamily: "IBM Plex Mono, monospace", captionStyle: "Graph paper", motionPreset: "blueprint-draw", colorGrade: "blueprint cool"}),
  sketch_post_it: base({accent: "#fef08a", secondary: "#fbcfe8", caption: "idea", caption2: "ship", fontFamily: "Caveat, cursive", captionStyle: "Post-it notes", motionPreset: "post-it-pop", colorGrade: "sketch warm"}),
  prism_pro_pricing: base({accent: "#a7f36b", secondary: "#67e8f9", caption: "Pro $29", caption2: "highlighted plan", fontFamily: "Outfit, sans-serif", captionStyle: "Price label", motionPreset: "price-pop", colorGrade: "prism clean"}),
  chalk_word_emphasis: base({accent: "#e2e8f0", secondary: "#94a3b8", caption: "emphasis", caption2: "chalk on dark", fontFamily: "Permanent Marker, cursive", captionStyle: "Chalk handwriting", motionPreset: "chalk-scribble", colorGrade: "chalk dark board"}),
  techtalk_intel_brief: base({accent: "#2dd4bf", secondary: "#e2e8f0", caption: "Key takeaway", caption2: "edu-finance brief", fontFamily: "IBM Plex Sans, sans-serif", captionStyle: "Weighted edu-finance captions", motionPreset: "intel-lower-third", colorGrade: "clean teal grade"}),
  swiss_grid_explainer: base({accent: "#111111", secondary: "#facc15", caption: "Step one", caption2: "Swiss grid flow", fontFamily: "Inter, sans-serif", captionStyle: "Swiss grid steps", motionPreset: "grid-reveal", colorGrade: "neutral swiss"}),
  vignelli_portrait_headline: base({accent: "#f8fafc", secondary: "#111111", caption: "BIG HEADLINE", caption2: "portrait stack", fontFamily: "Oswald, sans-serif", captionStyle: "Portrait headline", motionPreset: "headline-rise", colorGrade: "bold portrait"}),
  decision_tree_tutorial: base({accent: "#38bdf8", secondary: "#bae6fd", caption: "If this", caption2: "then that", fontFamily: "IBM Plex Mono, monospace", captionStyle: "Decision tree", motionPreset: "node-pop", colorGrade: "tutorial cool"}),
  kinetic_type_promo: base({accent: "#f472b6", secondary: "#22d3ee", caption: "GO", caption2: "FASTER", fontFamily: "Bebas Neue, sans-serif", captionStyle: "Kinetic swap", motionPreset: "word-swap", colorGrade: "kinetic punch"}),
  nyt_graph_data_story: base({accent: "#ef4444", secondary: "#facc15", caption: "+12%", caption2: "chart story", fontFamily: "Libre Baskerville, serif", captionStyle: "Chart annotation", motionPreset: "chart-draw", colorGrade: "editorial data"}),
  eva_neon_cyber: base({accent: "#ff2a85", secondary: "#00f3ff", caption: "CYBER", caption2: "scanline neon", fontFamily: "Syne, sans-serif", captionStyle: "Cyber neon", motionPreset: "cyber-glitch", colorGrade: "cyber neon"}),
  volt_lime_kinetic: base({accent: "#a3e635", secondary: "#22c55e", caption: "VOLT", caption2: "lime impact", fontFamily: "Archivo Black, sans-serif", captionStyle: "Lime impact", motionPreset: "volt-slam", colorGrade: "volt lime"}),
  ember_sunset_gradient: base({accent: "#ff5e36", secondary: "#facc15", caption: "warm glow", caption2: "sunset script", fontFamily: "Fraunces, serif", captionStyle: "Sunset script", motionPreset: "ember-glow", colorGrade: "sunset warm"}),
  studio_kinetic_reel: base({accent: "#00f5a0", secondary: "#00d2ff", caption: "SCALE 10X", caption2: "kinetic reel impact", fontFamily: "Outfit, sans-serif", captionStyle: "Kinetic punch hierarchy", motionPreset: "kinetic-reel", colorGrade: "studio kinetic"}),
};

export function getRecipeTheme(templateId: string): RecipeTheme {
  return recipeThemes[templateId] || recipeThemes.spiritual_reflective;
}
