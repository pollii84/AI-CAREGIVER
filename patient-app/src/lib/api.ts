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
export const DEV_PATIENT_ID = '8d6aaa97-cf22-4654-9146-6de1826a4fa1';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
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
