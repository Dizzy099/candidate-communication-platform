// Shapes returned by the Django API (see backend serializers).

export type MessageStatus =
  | "scheduled"
  | "queued"
  | "sending"
  | "sent"
  | "delivered"
  | "read"
  | "failed"
  | "cancelled";

export interface LastMessage {
  id: string;
  status: MessageStatus;
  status_label: string;
  created_at: string;
}

export interface Candidate {
  id: number;
  candidate_code: string;
  full_name: string;
  phone: string;
  phone_display: string;
  email: string;
  created_at: string;
  last_message: LastMessage | null;
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface MessageError {
  category: string;
  code: string;
  title: string;
  explanation: string;
  technical_detail: string;
}

export interface MessageEvent {
  id: number;
  kind: string;
  kind_label: string;
  source: "system" | "provider";
  status: string;
  detail: string;
  applied: boolean;
  occurred_at: string;
}

export interface MessageAttempt {
  number: number;
  trigger: "initial" | "auto_retry" | "manual_retry";
  outcome: "in_progress" | "accepted" | "failed";
  error_category: string;
  error_code: string;
  http_status: number | null;
  retry_after_seconds: number | null;
  provider_message_id: string | null;
  started_at: string;
  finished_at: string | null;
}

export interface Message {
  id: string;
  candidate_id: number;
  batch_id: string | null;
  body: string;
  channel: string;
  provider: string;
  provider_label: string;
  status: MessageStatus;
  status_label: string;
  provider_message_id: string | null;
  attempt_count: number;
  max_attempts: number;
  next_attempt_at: string | null;
  retry_scheduled: boolean;
  error: MessageError | null;
  can_retry: boolean;
  retry_block_reason: string | null;
  can_cancel: boolean;
  created_at: string;
  scheduled_at: string | null;
  sent_at: string | null;
  delivered_at: string | null;
  read_at: string | null;
  failed_at: string | null;
  cancelled_at: string | null;
  updated_at: string;
}

export interface MessageDetail extends Message {
  events: MessageEvent[];
  attempts: MessageAttempt[];
}

export interface RecipientCandidate {
  id: number;
  candidate_code: string;
  full_name: string;
  phone_display: string;
}

export interface BatchMessage extends Message {
  candidate: RecipientCandidate;
}

export interface BatchSummary {
  total: number;
  processing: number;
  scheduled: number;
  submitted: number;
  delivered: number;
  read: number;
  failed: number;
  cancelled: number;
  retrying: number;
  complete: boolean;
}

export interface Batch {
  id: string;
  body: string;
  channel: string;
  provider: string;
  recipient_count: number;
  scheduled_at: string | null;
  created_at: string;
  summary: BatchSummary;
  messages: BatchMessage[];
}

export interface Template {
  id: number;
  name: string;
  body: string;
  created_at: string;
  updated_at: string;
}

export interface TemplateVariable {
  name: string;
  token: string;
  description: string;
}

export interface ProviderInfo {
  name: string;
  display_name: string;
  channel: string;
  simulated: boolean;
  status: "operational" | "degraded" | "unavailable";
  detail: string;
  checked_at: string;
}

export interface ProviderHealth {
  status: "operational" | "degraded" | "unavailable";
  detail: string;
  checked_at: string;
  default_provider: string;
  providers: ProviderInfo[];
  stats: {
    total: number;
    sent: number;
    delivered: number;
    read: number;
    failed: number;
    in_progress: number;
    scheduled: number;
  };
  demo_controls_enabled: boolean;
  scenarios: { channel: string; match: string; behaviour: string }[];
}

export interface NewCandidate {
  full_name: string;
  phone: string;
  email: string;
}

export interface SendPayload {
  body: string;
  client_request_id: string;
  template_id?: number | null;
  scheduled_at?: string | null;
  provider?: string;
}
