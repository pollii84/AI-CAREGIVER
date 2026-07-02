import { useCallback, useState } from 'react';
import { useFocusEffect } from 'expo-router';
import { ActivityIndicator, Pressable, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { BottomTabInset, MaxContentWidth, MinTouchTarget, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { api, DEV_PATIENT_ID, type Checkin, type Medication } from '@/lib/api';

// Product/UX doc §3.1a: mood-row entries are a distinct checkin_type from
// the structured flow, feeding the same get_checkin_history data — see
// 04-Database/DATABASE_DESIGN.md §3.2. SVG-equivalent faces, not literal
// emoji glyphs (`no-emoji-icons` rule) — using labeled Pressables here
// since sourcing 5 custom SVGs is out of scope for this scaffold pass.
const MOODS = [
  { key: 'bad', label: 'Bad' },
  { key: 'not_great', label: 'Not great' },
  { key: 'okay', label: 'Okay' },
  { key: 'good', label: 'Good' },
  { key: 'great', label: 'Great' },
] as const;

// "Today" screen — Product/UX doc §3.1: the 0-decision landing screen.
// Everything actionable is a single glanceable card, nothing requires
// reading. Fetches real data from the backend on every focus (not just
// mount) so returning from Check-in/Voice Log shows fresh state.
export default function TodayScreen() {
  const theme = useTheme();
  const [medications, setMedications] = useState<Medication[] | null>(null);
  const [checkins, setCheckins] = useState<Checkin[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submittingMood, setSubmittingMood] = useState(false);

  const refresh = useCallback(() => {
    setError(null);
    return Promise.all([api.listMedications(DEV_PATIENT_ID), api.listCheckins(DEV_PATIENT_ID)])
      .then(([meds, chk]) => {
        setMedications(meds);
        setCheckins(chk);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : String(err));
      });
  }, []);

  useFocusEffect(
    useCallback(() => {
      let cancelled = false;
      refresh().catch(() => {
        // error already captured in state by refresh()
      });
      return () => {
        cancelled = true;
        void cancelled;
      };
    }, [refresh])
  );

  const todayCheckin = checkins?.find((c) => isToday(c.recorded_at));
  const todayMood = checkins?.find((c) => c.checkin_type === 'mood_row' && isToday(c.recorded_at));
  const loading = medications === null && checkins === null && error === null;

  async function submitMood(moodKey: string) {
    setSubmittingMood(true);
    try {
      await api.submitCheckin(DEV_PATIENT_ID, {
        checkin_type: 'mood_row',
        answers: { mood: moodKey },
        input_mode: 'text',
      });
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmittingMood(false);
    }
  }

  return (
    <ThemedView style={styles.container}>
      <SafeAreaView style={styles.safeArea} edges={['top']}>
        <ThemedText type="title" style={styles.title}>
          Today
        </ThemedText>

        {loading && <ActivityIndicator style={styles.spinner} />}

        {error && (
          <ThemedView type="backgroundElement" style={styles.card}>
            <ThemedText themeColor="destructive" type="smallBold">
              Could not reach the backend
            </ThemedText>
            <ThemedText type="small" themeColor="textSecondary" style={styles.errorDetail}>
              {error}
            </ThemedText>
            <ThemedText type="small" themeColor="textSecondary">
              Check that the API is running (backend/README.md) and DEV_PATIENT_ID in src/lib/api.ts
              matches a real patient.
            </ThemedText>
          </ThemedView>
        )}

        {!loading && !error && (
          <>
            <ThemedView type="backgroundElement" style={styles.card}>
              <ThemedText type="smallBold">Check-in status</ThemedText>
              <ThemedText style={styles.cardBody}>
                {todayCheckin ? 'Done for today' : 'Not checked in yet today'}
              </ThemedText>
            </ThemedView>

            <ThemedView type="backgroundElement" style={styles.card}>
              <ThemedText type="smallBold">How are you feeling today?</ThemedText>
              {todayMood ? (
                <ThemedText type="small" themeColor="textSecondary" style={styles.cardBody}>
                  Logged: {String(todayMood.answers.mood)}
                </ThemedText>
              ) : (
                <ThemedView style={styles.moodRow}>
                  {MOODS.map((m) => (
                    <Pressable
                      key={m.key}
                      disabled={submittingMood}
                      onPress={() => submitMood(m.key)}
                      style={({ pressed }) => [
                        styles.moodButton,
                        { backgroundColor: pressed ? theme.backgroundSelected : theme.background },
                      ]}>
                      <ThemedText type="small" style={styles.moodLabel}>
                        {m.label}
                      </ThemedText>
                    </Pressable>
                  ))}
                </ThemedView>
              )}
            </ThemedView>

            <ThemedView type="backgroundElement" style={styles.card}>
              <ThemedText type="smallBold">Medications ({medications?.length ?? 0})</ThemedText>
              {medications && medications.length > 0 ? (
                medications.map((m) => (
                  <ThemedText key={m.id} style={styles.cardBody}>
                    {m.name} — {m.dosage}
                  </ThemedText>
                ))
              ) : (
                <ThemedText type="small" themeColor="textSecondary" style={styles.cardBody}>
                  No medications on file yet.
                </ThemedText>
              )}
            </ThemedView>
          </>
        )}
      </SafeAreaView>
    </ThemedView>
  );
}

function isToday(iso: string): boolean {
  const d = new Date(iso);
  const now = new Date();
  return d.toDateString() === now.toDateString();
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  safeArea: {
    flex: 1,
    paddingHorizontal: Spacing.four,
    paddingBottom: BottomTabInset,
    gap: Spacing.three,
    maxWidth: MaxContentWidth,
    alignSelf: 'center',
    width: '100%',
  },
  title: { marginTop: Spacing.three },
  spinner: { marginTop: Spacing.five },
  card: {
    borderRadius: Spacing.three,
    padding: Spacing.three,
    gap: Spacing.one,
  },
  cardBody: { marginTop: Spacing.half },
  errorDetail: { marginBottom: Spacing.one },
  moodRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.two,
    marginTop: Spacing.one,
  },
  moodButton: {
    minHeight: MinTouchTarget,
    minWidth: MinTouchTarget,
    paddingHorizontal: Spacing.two,
    borderRadius: Spacing.two,
    alignItems: 'center',
    justifyContent: 'center',
  },
  moodLabel: { textAlign: 'center' },
});
