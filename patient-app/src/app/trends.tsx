import { useCallback, useState } from 'react';
import { useFocusEffect } from 'expo-router';
import { ActivityIndicator, FlatList, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { BottomTabInset, MaxContentWidth, Spacing } from '@/constants/theme';
import { api, DEV_PATIENT_ID, type Checkin } from '@/lib/api';

// Product/UX doc §6: compliance-critical framing. Header reads "Your Logged
// History", never "Progress" or "Status" — those imply a clinical
// judgment. Raw scale values only, NEVER a color-coded good/bad indicator —
// that's exactly what PRD Open Risk #1 says to avoid. Do not add a
// red/green/traffic-light treatment here without revisiting that doc first.
export default function TrendsScreen() {
  const [checkins, setCheckins] = useState<Checkin[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useFocusEffect(
    useCallback(() => {
      let cancelled = false;
      api
        .listCheckins(DEV_PATIENT_ID)
        .then((data) => !cancelled && setCheckins(data))
        .catch((err) => !cancelled && setError(err instanceof Error ? err.message : String(err)));
      return () => {
        cancelled = true;
      };
    }, [])
  );

  return (
    <ThemedView style={styles.container}>
      <SafeAreaView style={styles.safeArea} edges={['top']}>
        <ThemedText type="title" style={styles.title}>
          Your Logged History
        </ThemedText>

        {error && (
          <ThemedText themeColor="destructive" type="small">
            {error}
          </ThemedText>
        )}

        {checkins === null && !error && <ActivityIndicator style={styles.spinner} />}

        {checkins?.length === 0 && (
          <ThemedText themeColor="textSecondary" style={styles.empty}>
            No check-ins logged yet.
          </ThemedText>
        )}

        <FlatList
          data={checkins ?? []}
          keyExtractor={(c) => c.id}
          contentContainerStyle={styles.list}
          renderItem={({ item }) => (
            <ThemedView type="backgroundElement" style={styles.row}>
              <ThemedText type="smallBold">
                {item.checkin_type === 'structured' ? 'Full check-in' : 'Mood check-in'}
              </ThemedText>
              <ThemedText type="small" themeColor="textSecondary">
                {new Date(item.recorded_at).toLocaleString()}
              </ThemedText>
              {item.computed_score !== null && (
                <ThemedText type="small">Score: {item.computed_score}</ThemedText>
              )}
            </ThemedView>
          )}
        />
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
    maxWidth: MaxContentWidth,
    alignSelf: 'center',
    width: '100%',
  },
  title: { marginTop: Spacing.three, marginBottom: Spacing.two },
  spinner: { marginTop: Spacing.five },
  empty: { marginTop: Spacing.three },
  list: { gap: Spacing.two, paddingBottom: Spacing.three },
  row: { borderRadius: Spacing.two, padding: Spacing.three, gap: Spacing.half },
});
