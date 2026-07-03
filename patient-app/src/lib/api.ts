/**
 * Backend API client — talks to the FastAPI service in ../backend.
 *
 * TODO(auth): no session/auth layer exists yet on either side (see
 * backend/README.md "Known gaps"). `DEV_PATIENT_ID` stands in for what
 * should come from an authenticated session. Do not ship this constant —
 * replace with real auth before this app leaves local dev.
 *
 * Base URL points at the host loopback address. iOS Simulator shares the
 * host's network stack, so `127.0.0.1` reaches the backend directly — this
 * will NOT work on a physical device or Android emulator (Android emulator
 * needs `10.0.2.2`); switch to a LAN IP or tunnel for device testing.
 */

const API_BASE_URL = 'http://127.0.0.1:8000/api/v1';

// Set after onboarding in a real build. Hardcoded for scaffold verification —
// create a patient first via the backend, then paste its id here.
export const DEV_PATIENT_ID = '9d15de79-d89a-48ee-bd83-8d1e0e6ee46a';

// Dev-only credentials for the patient above — the backend now requires a
// Bearer token on every patient route, so the client logs in lazily and
// caches the access token. Replace with real session auth before shipping.
const DEV_EMAIL = 'dev@patient.local';
const DEV_PASSWORD = 'DevPassword123!';

let accessToken: string | null = null;

async function ensureToken(): Promise<string> {
  if (accessToken) return accessToken;
  const res = await fetch(`${API_BASE_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: DEV_EMAIL, password: DEV_PASSWORD, role: 'patient' }),
  });
  if (!res.ok) {
    throw new Error(`dev login failed -> ${res.status}: ${await res.text().catch(() => '')}`);
  }
  const body = (await res.json()) as { access_token: string };
  accessToken = body.access_token;
  return accessToken;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = await ensureToken();
  const res = await fetch(`${API_BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    ...init,
  });
  if (res.status === 401) {
    // token expired (15-min access tokens) — re-login once and retry
    accessToken = null;
    const retryToken = await ensureToken();
    return requestWithToken<T>(path, retryToken, init);
  }
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`${init?.method ?? 'GET'} ${path} -> ${res.status}: ${body}`);
  }
  return res.json();
}

async function requestWithToken<T>(path: string, token: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`${init?.method ?? 'GET'} ${path} -> ${res.status}: ${body}`);
  }
  return res.json();
}

export type Patient = {
  id: string;
  disease_profile_id: string;
  preferred_comm_mode: string;
};

export type Medication = {
  id: string;
  name: string;
  dosage: string;
  schedule_rrule: string;
  active: boolean;
};

export type Checkin = {
  id: string;
  checkin_type: 'structured' | 'mood_row';
  answers: Record<string, unknown>;
  computed_score: number | null;
  input_mode: 'text' | 'voice';
  recorded_at: string;
};

export type AgentReply = {
  answer: string;
  citations: { source_id: string; title: string; corpus_or_trial: 'corpus' | 'trial' }[];
  disclaimer: string;
  escalate: boolean;
};

export const api = {
  getPatient: (patientId: string) => request<Patient>(`/patients/${patientId}`),

  listMedications: (patientId: string) => request<Medication[]>(`/patients/${patientId}/medications`),

  listCheckins: (patientId: string) => request<Checkin[]>(`/patients/${patientId}/checkins`),

  submitCheckin: (
    patientId: string,
    body: { checkin_type: 'structured' | 'mood_row'; answers: Record<string, unknown>; input_mode: 'text' | 'voice' }
  ) =>
    request<Checkin>(`/patients/${patientId}/checkins`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  startConversation: (patientId: string) =>
    request<{ conversation_id: string }>(`/patients/${patientId}/agent/conversations`, { method: 'POST' }),

  sendMessage: (patientId: string, conversationId: string, message: string) =>
    request<AgentReply>(`/patients/${patientId}/agent/conversations/${conversationId}/messages`, {
      method: 'POST',
      body: JSON.stringify({ message }),
    }),
};
