/**
 * Brand palette — 03-Product-UX-Design-Frontend/PRODUCT_UX_DESIGN.md §1.
 * Same tokens as the marketing site (calm cyan + health green), so the
 * patient app and the public site read as one product.
 */

import '@/global.css';

import { Platform } from 'react-native';

export const Colors = {
  light: {
    text: '#164e63',
    background: '#ecfeff',
    backgroundElement: '#e8f1f6',
    backgroundSelected: '#a5f3fc',
    textSecondary: '#164e63aa',
    primary: '#0891b2',
    onPrimary: '#ffffff',
    accent: '#059669',
    destructive: '#dc2626',
  },
  dark: {
    text: '#e8f1f6',
    background: '#0b1e24',
    backgroundElement: '#123039',
    backgroundSelected: '#164e63',
    textSecondary: '#e8f1f6aa',
    primary: '#22d3ee',
    onPrimary: '#0b1e24',
    accent: '#34d399',
    destructive: '#f87171',
  },
} as const;

export type ThemeColor = keyof typeof Colors.light & keyof typeof Colors.dark;

export const Fonts = Platform.select({
  ios: {
    /** iOS `UIFontDescriptorSystemDesignDefault` */
    sans: 'system-ui',
    /** iOS `UIFontDescriptorSystemDesignSerif` */
    serif: 'ui-serif',
    /** iOS `UIFontDescriptorSystemDesignRounded` */
    rounded: 'ui-rounded',
    /** iOS `UIFontDescriptorSystemDesignMonospaced` */
    mono: 'ui-monospace',
  },
  default: {
    sans: 'normal',
    serif: 'serif',
    rounded: 'normal',
    mono: 'monospace',
  },
  web: {
    sans: 'var(--font-display)',
    serif: 'var(--font-serif)',
    rounded: 'var(--font-rounded)',
    mono: 'var(--font-mono)',
  },
});

// Spacing scale widened slightly vs. Expo defaults — Product/UX doc §2:
// touch targets >=44x44pt, comfortable spacing for tremor-affected input.
export const Spacing = {
  half: 2,
  one: 4,
  two: 8,
  three: 16,
  four: 24,
  five: 32,
  six: 64,
} as const;

export const BottomTabInset = Platform.select({ ios: 50, android: 80 }) ?? 0;
export const MaxContentWidth = 800;

// Product/UX doc §2: touch targets >=44x44pt.
export const MinTouchTarget = 44;
