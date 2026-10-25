export const CHANNEL_LABEL: Record<string, string> = { sms: "SMS", email: "Email" };

export function channelLabel(channel: string): string {
  return CHANNEL_LABEL[channel] ?? channel;
}

/** "SimuText (simulated SMS provider)" -> "SimuText" */
export function shortProviderName(displayName: string): string {
  return displayName.replace(/\s*\(.*\)\s*$/, "");
}
