// Formatting used across the UI. Dates follow the design: DD-MM-YYYY, 9:47 AM.

const pad = (value: number) => String(value).padStart(2, "0");

export function formatDate(iso: string): string {
  const date = new Date(iso);
  return `${pad(date.getDate())}-${pad(date.getMonth() + 1)}-${date.getFullYear()}`;
}

export function formatTime(iso: string): string {
  const date = new Date(iso);
  const hours = date.getHours();
  const suffix = hours >= 12 ? "PM" : "AM";
  return `${hours % 12 || 12}:${pad(date.getMinutes())} ${suffix}`;
}

export function formatTimeWithSeconds(iso: string): string {
  const date = new Date(iso);
  const hours = date.getHours();
  return `${hours % 12 || 12}:${pad(date.getMinutes())}:${pad(date.getSeconds())} ${hours >= 12 ? "PM" : "AM"}`;
}

export function formatDateTime(iso: string): string {
  return `${formatDate(iso)}, ${formatTime(iso)}`;
}

export function plural(count: number, singular: string, pluralForm = `${singular}s`): string {
  return `${count} ${count === 1 ? singular : pluralForm}`;
}

/** Value for <input type="datetime-local"> in the browser's local time zone. */
export function toLocalInputValue(date: Date): string {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

/** Parse a datetime-local value as local time and return an ISO string with offset (UTC). */
export function localInputToIso(value: string): string | null {
  if (!value) return null;
  const date = new Date(value); // datetime-local strings are parsed as local time
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

export function firstName(fullName: string): string {
  return fullName.split(" ")[0] ?? fullName;
}
