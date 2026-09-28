export function friendlyTemplateStatus(status?: string) {
  const normalized = (status || "").trim().toLowerCase();
  if (!normalized || normalized === "ready" || normalized === "production-ready") return "Ready";
  if (normalized === "draft") return "Draft";
  if (normalized === "experimental" || normalized === "beta") return "Beta";
  if (normalized === "unavailable" || normalized === "error") return "Unavailable";
  if (normalized === "deprecated") return "Legacy";
  return status ? "Available" : "Ready";
}
