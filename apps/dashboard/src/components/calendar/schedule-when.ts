export function padTime(value: number): string {
  return String(value).padStart(2, "0");
}

export function toJakartaDatetimeLocal(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Jakarta",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(date);
  const get = (type: string) => parts.find((part) => part.type === type)?.value || "";
  return `${get("year")}-${get("month")}-${get("day")}T${get("hour")}:${get("minute")}`;
}

export function fromJakartaDatetimeLocal(value: string): string {
  return value.length === 16 ? `${value}:00+07:00` : `${value}+07:00`;
}

export function nextJakartaSlot(hour: number, minute: number): string {
  const now = new Date();
  const datePart = toJakartaDatetimeLocal(now.toISOString()).slice(0, 10);
  const today = `${datePart}T${padTime(hour)}:${padTime(minute)}:00+07:00`;
  if (new Date(today).getTime() > now.getTime()) {
    return today;
  }
  const noon = new Date(`${datePart}T12:00:00+07:00`);
  const nextDate = toJakartaDatetimeLocal(new Date(noon.getTime() + 24 * 60 * 60 * 1000).toISOString()).slice(0, 10);
  return `${nextDate}T${padTime(hour)}:${padTime(minute)}:00+07:00`;
}

export function nextCadenceSlot(): string {
  const morning = nextJakartaSlot(9, 0);
  const evening = nextJakartaSlot(19, 30);
  return new Date(morning).getTime() <= new Date(evening).getTime() ? morning : evening;
}
