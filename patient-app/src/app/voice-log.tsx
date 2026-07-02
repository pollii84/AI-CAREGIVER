import { StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { BottomTabInset, MaxContentWidth, Spacing } from '@/constants/theme';

// Placeholder — Product/UX doc §3.1: center quick-action for instant voice
// capture (symptom note, quick question, or ad-hoc check-in item). Not
// wired to real speech input: no voice framework/vendor has been chosen yet
// (Product/UX doc §8 Open Item #1, backend/README "Known gaps"). Ship this
// honestly as "coming soon," not a fake-functional mic button.
export default function VoiceLogScreen() {
  return (
    <ThemedView style={styles.container}>
      <SafeAreaView style={styles.safeArea} edges={['top']}>
        <ThemedText type="title">Voice Log</ThemedText>
        <ThemedText style={styles.body} themeColor="textSecondary">
          Voice capture is coming soon — no voice input framework has been
          selected yet. For now, use Check-in or Care Agent (text input) to
          log something.
        </ThemedText>
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
  body: { marginTop: Spacing.two },
});
