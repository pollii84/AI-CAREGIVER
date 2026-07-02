import { NativeTabs } from 'expo-router/unstable-native-tabs';
import { useColorScheme } from 'react-native';

import { Colors } from '@/constants/theme';

// Product/UX doc §3.1: 5-tab nav w/ a center "quick action" slot, adapted
// from Lovi's raised center-tab pattern. NativeTabs (native UITabBar
// wrapper) has no "raised/floating" button primitive the way a JS-rendered
// custom tab bar would — `NativeTabs.BottomAccessory` exists but its exact
// press/navigation semantics aren't confirmed offline, so Voice Log ships
// here as a plain 5th tab (fully reachable in one tap, just not visually
// raised). Revisit BottomAccessory for the raised treatment once verified.
export default function AppTabs() {
  const scheme = useColorScheme();
  const colors = Colors[scheme === 'unspecified' ? 'light' : (scheme ?? 'light')];

  return (
    <NativeTabs
      backgroundColor={colors.background}
      indicatorColor={colors.backgroundElement}
      labelStyle={{ selected: { color: colors.text } }}>
      <NativeTabs.Trigger name="index">
        <NativeTabs.Trigger.Label>Today</NativeTabs.Trigger.Label>
        <NativeTabs.Trigger.Icon sf="house.fill" md="home" />
      </NativeTabs.Trigger>

      <NativeTabs.Trigger name="checkin">
        <NativeTabs.Trigger.Label>Check-in</NativeTabs.Trigger.Label>
        <NativeTabs.Trigger.Icon sf="checklist" md="checklist" />
      </NativeTabs.Trigger>

      <NativeTabs.Trigger name="voice-log">
        <NativeTabs.Trigger.Label>Voice Log</NativeTabs.Trigger.Label>
        <NativeTabs.Trigger.Icon sf="mic.fill" md="mic" />
      </NativeTabs.Trigger>

      <NativeTabs.Trigger name="care-agent">
        <NativeTabs.Trigger.Label>Care Agent</NativeTabs.Trigger.Label>
        <NativeTabs.Trigger.Icon sf="bubble.left.and.bubble.right.fill" md="chat" />
      </NativeTabs.Trigger>

      <NativeTabs.Trigger name="trends">
        <NativeTabs.Trigger.Label>Trends</NativeTabs.Trigger.Label>
        <NativeTabs.Trigger.Icon sf="chart.line.uptrend.xyaxis" md="trending_up" />
      </NativeTabs.Trigger>
    </NativeTabs>
  );
}
