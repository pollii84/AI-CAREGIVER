import { useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Alert, FlatList, KeyboardAvoidingView, Platform, Pressable, StyleSheet, TextInput } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { BottomTabInset, MaxContentWidth, MinTouchTarget, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { api, DEV_PATIENT_ID, type AgentReply } from '@/lib/api';

type Message = { role: 'user' | 'agent'; text: string; reply?: AgentReply };

// Care Agent conversation UI — Product/UX doc §4. Every agent message that
// carries a factual claim renders as a card with tappable citation chips
// and a fixed disclaimer, never a bare bubble. Escalation surfaces a
// "Talk to your care team" CTA instead of a dead end.
export default function CareAgentScreen() {
  const theme = useTheme();
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const listRef = useRef<FlatList>(null);

  useEffect(() => {
    api
      .startConversation(DEV_PATIENT_ID)
      .then((res) => setConversationId(res.conversation_id))
      .catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, []);

  async function send() {
    const text = input.trim();
    if (!text || !conversationId || sending) return;

    setMessages((prev) => [...prev, { role: 'user', text }]);
    setInput('');
    setSending(true);
    setError(null);

    try {
      const reply = await api.sendMessage(DEV_PATIENT_ID, conversationId, text);
      setMessages((prev) => [...prev, { role: 'agent', text: reply.answer, reply }]);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSending(false);
      requestAnimationFrame(() => listRef.current?.scrollToEnd({ animated: true }));
    }
  }

  return (
    <ThemedView style={styles.container}>
      <SafeAreaView style={styles.safeArea} edges={['top']}>
        <ThemedText type="title" style={styles.title}>
          Care Agent
        </ThemedText>

        <FlatList
          ref={listRef}
          data={messages}
          keyExtractor={(_, i) => String(i)}
          contentContainerStyle={styles.messages}
          renderItem={({ item }) =>
            item.role === 'user' ? (
              <ThemedView style={[styles.bubble, styles.userBubble, { backgroundColor: theme.primary }]}>
                <ThemedText style={{ color: theme.onPrimary }}>{item.text}</ThemedText>
              </ThemedView>
            ) : (
              <ThemedView type="backgroundElement" style={[styles.bubble, styles.agentCard]}>
                <ThemedText>{item.text}</ThemedText>

                {item.reply && item.reply.citations.length > 0 && (
                  <ThemedView style={styles.citations}>
                    {item.reply.citations.map((c: NonNullable<Message['reply']>['citations'][number]) => (
                      // Product/UX doc §4/§7: citation chips must be tappable, never
                      // silently trust-me text. Backend today only returns
                      // source_id/title/corpus_or_trial (no snippet/link, no
                      // clinician_reviewed flag on this response — see
                      // backend/app/agent/schema.py) so the tap target surfaces what
                      // data actually exists rather than fabricating a "MD Verified"
                      // checkmark or a snippet the API doesn't send. hitSlop widens
                      // the touch target to ~44pt without inflating the compact chip
                      // visual (Product/UX doc §2 touch-target minimum).
                      <Pressable
                        key={c.source_id}
                        hitSlop={{ top: 10, bottom: 10, left: 8, right: 8 }}
                        onPress={() =>
                          Alert.alert(
                            c.title,
                            c.corpus_or_trial === 'corpus'
                              ? 'Source: clinical corpus (guideline / literature).\n\nFull source detail (snippet, link) isn’t available yet — the backend only returns the title and source type today.'
                              : 'Source: clinical trial (ClinicalTrials.gov).\n\nFull source detail (snippet, link) isn’t available yet — the backend only returns the title and source type today.'
                          )
                        }
                        style={({ pressed }) => [
                          styles.chip,
                          { backgroundColor: theme.backgroundSelected, opacity: pressed ? 0.6 : 1 },
                        ]}>
                        <ThemedText type="small">{c.title}</ThemedText>
                      </Pressable>
                    ))}
                  </ThemedView>
                )}

                {item.reply?.disclaimer && (
                  <ThemedText type="small" themeColor="textSecondary" style={styles.disclaimer}>
                    &#9432; {item.reply.disclaimer}
                  </ThemedText>
                )}

                {item.reply?.escalate && (
                  <ThemedView style={[styles.escalateCta, { backgroundColor: theme.destructive }]}>
                    <ThemedText style={{ color: theme.onPrimary }} type="smallBold">
                      Talk to your care team
                    </ThemedText>
                  </ThemedView>
                )}
              </ThemedView>
            )
          }
        />

        {error && (
          <ThemedText themeColor="destructive" type="small" style={styles.error}>
            {error}
          </ThemedText>
        )}

        <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
          <ThemedView style={styles.inputRow}>
            <TextInput
              value={input}
              onChangeText={setInput}
              placeholder="Ask a question…"
              placeholderTextColor={theme.textSecondary}
              style={[styles.input, { color: theme.text, backgroundColor: theme.backgroundElement }]}
              editable={!sending && !!conversationId}
              onSubmitEditing={send}
              returnKeyType="send"
            />
            <Pressable
              onPress={send}
              disabled={sending || !conversationId || !input.trim()}
              style={[styles.sendButton, { backgroundColor: theme.primary, opacity: sending ? 0.6 : 1 }]}>
              {sending ? <ActivityIndicator color={theme.onPrimary} /> : <ThemedText style={{ color: theme.onPrimary }}>Send</ThemedText>}
            </Pressable>
          </ThemedView>
        </KeyboardAvoidingView>
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
  messages: { gap: Spacing.two, paddingBottom: Spacing.three },
  bubble: { borderRadius: Spacing.three, padding: Spacing.three, maxWidth: '90%' },
  userBubble: { alignSelf: 'flex-end' },
  agentCard: { alignSelf: 'flex-start', gap: Spacing.two },
  citations: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.one },
  chip: { paddingHorizontal: Spacing.two, paddingVertical: Spacing.half, borderRadius: Spacing.four },
  disclaimer: {},
  escalateCta: {
    borderRadius: Spacing.two,
    paddingVertical: Spacing.two,
    paddingHorizontal: Spacing.three,
    alignItems: 'center',
    minHeight: MinTouchTarget,
    justifyContent: 'center',
  },
  error: { marginBottom: Spacing.one },
  inputRow: { flexDirection: 'row', gap: Spacing.two, paddingVertical: Spacing.two },
  input: {
    flex: 1,
    minHeight: MinTouchTarget,
    borderRadius: Spacing.three,
    paddingHorizontal: Spacing.three,
  },
  sendButton: {
    minWidth: MinTouchTarget,
    minHeight: MinTouchTarget,
    borderRadius: Spacing.three,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: Spacing.three,
  },
});
