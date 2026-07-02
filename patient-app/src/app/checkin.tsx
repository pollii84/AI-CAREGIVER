import { useState } from 'react';
import { useRouter } from 'expo-router';
import { Pressable, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { BottomTabInset, MaxContentWidth, MinTouchTarget, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { api, DEV_PATIENT_ID } from '@/lib/api';

// TODO(backend): no GET /disease-profiles/:id endpoint exists yet, so the
// question set is hardcoded here from db/schema.sql's Parkinson's seed row
// (rating_scale_config) rather than fetched. Real disease-pluggability
// (Architecture doc §5) needs this to come from the API.
const QUESTIONS = [
  {
    id: 'medication_on_time',
    prompt: 'Did you take your medication on time today?',
    options: ['Yes', 'No', 'Not yet'],
  },
  {
    id: 'falls',
    prompt: 'Any falls or near-falls since your last check-in?',
    options: ['No', 'Yes'],
  },
  {
    id: 'movement_today',
    prompt: 'How are your movements today?',
    options: ['1', '2', '3', '4', '5'],
  },
] as const;

// Product/UX doc §5: sequential, linear, one decision per screen. Back
// navigation preserves prior answers. A "Yes" on the falls question is the
// one intentional branch (safety over consistency) — flagged here, not yet
// wired to the emergency path (that's the Care Agent chat's job today; a
// direct sensor/checkin-triggered alert is a follow-up).
export default function CheckinScreen() {
  const theme = useTheme();
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const question = QUESTIONS[step];

  async function selectAnswer(value: string) {
    const nextAnswers = { ...answers, [question.id]: value };
    setAnswers(nextAnswers);

    if (step < QUESTIONS.length - 1) {
      setStep(step + 1);
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      await api.submitCheckin(DEV_PATIENT_ID, {
        checkin_type: 'structured',
        answers: nextAnswers,
        input_mode: 'text',
      });
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  }

  if (done) {
    return (
      <ThemedView style={styles.container}>
        <SafeAreaView style={styles.safeArea} edges={['top']}>
          <ThemedText type="title">Check-in complete</ThemedText>
          <ThemedText style={styles.spaced}>Thanks — logged for today.</ThemedText>
          <Pressable
            onPress={() => {
              setStep(0);
              setAnswers({});
              setDone(false);
              router.navigate('/');
            }}
            style={[styles.primaryButton, { backgroundColor: theme.primary }]}>
            <ThemedText style={{ color: theme.onPrimary }}>Back to Today</ThemedText>
          </Pressable>
        </SafeAreaView>
      </ThemedView>
    );
  }

  return (
    <ThemedView style={styles.container}>
      <SafeAreaView style={styles.safeArea} edges={['top']}>
        <ThemedText type="small" themeColor="textSecondary">
          Question {step + 1} of {QUESTIONS.length}
        </ThemedText>
        <ThemedText type="title" style={styles.prompt}>
          {question.prompt}
        </ThemedText>

        {error && (
          <ThemedText themeColor="destructive" type="small">
            {error}
          </ThemedText>
        )}

        <ThemedView style={styles.options}>
          {question.options.map((opt) => (
            <Pressable
              key={opt}
              disabled={submitting}
              onPress={() => selectAnswer(opt)}
              style={({ pressed }) => [
                styles.optionButton,
                { backgroundColor: pressed ? theme.backgroundSelected : theme.backgroundElement },
              ]}>
              <ThemedText type="default">{opt}</ThemedText>
            </Pressable>
          ))}
        </ThemedView>

        {step > 0 && !submitting && (
          <Pressable onPress={() => setStep(step - 1)} style={styles.backButton}>
            <ThemedText themeColor="primary" type="small">
              &larr; Back
            </ThemedText>
          </Pressable>
        )}
      </SafeAreaView>
    </ThemedView>
  );
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
  prompt: { marginTop: Spacing.two },
  spaced: { marginTop: Spacing.two, marginBottom: Spacing.three },
  options: { gap: Spacing.two, marginTop: Spacing.two },
  optionButton: {
    minHeight: MinTouchTarget,
    borderRadius: Spacing.two,
    paddingHorizontal: Spacing.three,
    justifyContent: 'center',
  },
  backButton: { minHeight: MinTouchTarget, justifyContent: 'center' },
  primaryButton: {
    minHeight: MinTouchTarget,
    borderRadius: Spacing.two,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: Spacing.four,
    alignSelf: 'flex-start',
  },
});
