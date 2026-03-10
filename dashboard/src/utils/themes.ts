/**
 * Theme configurations for the Orchestly Platform
 * Includes Light (default), Monokai Pro, Dracula, Nord, and One Dark themes
 */

export interface Theme {
  name: string;
  displayName: string;
  isDark: boolean;
  colors: {
    bgPrimary: string;
    bgSecondary: string;
    bgTertiary: string;
    bgHover: string;
    bgActive: string;
    textPrimary: string;
    textSecondary: string;
    textTertiary: string;
    textInverse: string;
    borderPrimary: string;
    borderSecondary: string;
    accent: string;
    accentHover: string;
    success: string;
    warning: string;
    error: string;
    info: string;
    pink: string;
    green: string;
    yellow: string;
    orange: string;
    purple: string;
    cyan: string;
    red: string;
  };
  shadows: {
    sm: string;
    md: string;
    lg: string;
  };
}

export const lightTheme: Theme = {
  name: 'light',
  displayName: 'Light',
  isDark: false,
  colors: {
    bgPrimary: '#ffffff',
    bgSecondary: '#f9fafb',
    bgTertiary: '#f3f4f6',
    bgHover: '#f9fafb',
    bgActive: '#e5e7eb',
    textPrimary: '#111827',
    textSecondary: '#6b7280',
    textTertiary: '#9ca3af',
    textInverse: '#ffffff',
    borderPrimary: '#e5e7eb',
    borderSecondary: '#d1d5db',
    accent: '#4f46e5',
    accentHover: '#4338ca',
    success: '#10b981',
    warning: '#f59e0b',
    error: '#ef4444',
    info: '#3b82f6',
    pink: '#ec4899',
    green: '#10b981',
    yellow: '#f59e0b',
    orange: '#f97316',
    purple: '#8b5cf6',
    cyan: '#06b6d4',
    red: '#ef4444',
  },
  shadows: {
    sm: '0 1px 2px 0 rgb(0 0 0 / 0.05)',
    md: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
    lg: '0 10px 15px -3px rgb(0 0 0 / 0.1)',
  },
};

export const monokaiProTheme: Theme = {
  name: 'monokai-pro',
  displayName: 'Monokai Pro',
  isDark: true,
  colors: {
    bgPrimary: '#2d2a2e',
    bgSecondary: '#221f22',
    bgTertiary: '#19181a',
    bgHover: '#403e41',
    bgActive: '#5b595c',
    textPrimary: '#fcfcfa',
    textSecondary: '#c1c0c0',
    textTertiary: '#939293',
    textInverse: '#2d2a2e',
    borderPrimary: '#403e41',
    borderSecondary: '#5b595c',
    accent: '#fc9867',
    accentHover: '#fd8c4e',
    success: '#a9dc76',
    warning: '#ffd866',
    error: '#ff6188',
    info: '#78dce8',
    pink: '#ff6188',
    green: '#a9dc76',
    yellow: '#ffd866',
    orange: '#fc9867',
    purple: '#ab9df2',
    cyan: '#78dce8',
    red: '#ff6188',
  },
  shadows: {
    sm: '0 1px 2px 0 rgb(0 0 0 / 0.3)',
    md: '0 4px 6px -1px rgb(0 0 0 / 0.5)',
    lg: '0 10px 15px -3px rgb(0 0 0 / 0.7)',
  },
};

export const draculaTheme: Theme = {
  name: 'dracula',
  displayName: 'Dracula',
  isDark: true,
  colors: {
    bgPrimary: '#282a36',
    bgSecondary: '#21222c',
    bgTertiary: '#191a21',
    bgHover: '#44475a',
    bgActive: '#6272a4',
    textPrimary: '#f8f8f2',
    textSecondary: '#bfc6d4',
    textTertiary: '#6272a4',
    textInverse: '#282a36',
    borderPrimary: '#44475a',
    borderSecondary: '#6272a4',
    accent: '#bd93f9',
    accentHover: '#a77bfa',
    success: '#50fa7b',
    warning: '#f1fa8c',
    error: '#ff5555',
    info: '#8be9fd',
    pink: '#ff79c6',
    green: '#50fa7b',
    yellow: '#f1fa8c',
    orange: '#ffb86c',
    purple: '#bd93f9',
    cyan: '#8be9fd',
    red: '#ff5555',
  },
  shadows: {
    sm: '0 1px 2px 0 rgb(0 0 0 / 0.4)',
    md: '0 4px 6px -1px rgb(0 0 0 / 0.6)',
    lg: '0 10px 15px -3px rgb(0 0 0 / 0.8)',
  },
};

export const nordTheme: Theme = {
  name: 'nord',
  displayName: 'Nord',
  isDark: true,
  colors: {
    bgPrimary: '#2e3440',
    bgSecondary: '#3b4252',
    bgTertiary: '#232831',
    bgHover: '#434c5e',
    bgActive: '#4c566a',
    textPrimary: '#eceff4',
    textSecondary: '#d8dee9',
    textTertiary: '#a5b3c5',
    textInverse: '#2e3440',
    borderPrimary: '#434c5e',
    borderSecondary: '#4c566a',
    accent: '#88c0d0',
    accentHover: '#81a1c1',
    success: '#a3be8c',
    warning: '#ebcb8b',
    error: '#bf616a',
    info: '#81a1c1',
    pink: '#b48ead',
    green: '#a3be8c',
    yellow: '#ebcb8b',
    orange: '#d08770',
    purple: '#b48ead',
    cyan: '#88c0d0',
    red: '#bf616a',
  },
  shadows: {
    sm: '0 1px 2px 0 rgb(0 0 0 / 0.3)',
    md: '0 4px 6px -1px rgb(0 0 0 / 0.5)',
    lg: '0 10px 15px -3px rgb(0 0 0 / 0.7)',
  },
};

export const oneDarkTheme: Theme = {
  name: 'one-dark',
  displayName: 'One Dark',
  isDark: true,
  colors: {
    bgPrimary: '#282c34',
    bgSecondary: '#21252b',
    bgTertiary: '#1b1d23',
    bgHover: '#3e4451',
    bgActive: '#4d5566',
    textPrimary: '#abb2bf',
    textSecondary: '#9da5b4',
    textTertiary: '#5c6370',
    textInverse: '#282c34',
    borderPrimary: '#3e4451',
    borderSecondary: '#4d5566',
    accent: '#61afef',
    accentHover: '#528bce',
    success: '#98c379',
    warning: '#e5c07b',
    error: '#e06c75',
    info: '#61afef',
    pink: '#c678dd',
    green: '#98c379',
    yellow: '#e5c07b',
    orange: '#d19a66',
    purple: '#c678dd',
    cyan: '#56b6c2',
    red: '#e06c75',
  },
  shadows: {
    sm: '0 1px 2px 0 rgb(0 0 0 / 0.35)',
    md: '0 4px 6px -1px rgb(0 0 0 / 0.55)',
    lg: '0 10px 15px -3px rgb(0 0 0 / 0.75)',
  },
};

export const themes = {
  'light': lightTheme,
  'monokai-pro': monokaiProTheme,
  'dracula': draculaTheme,
  'nord': nordTheme,
  'one-dark': oneDarkTheme,
};

export type ThemeType = keyof typeof themes;

export const themeOptions = Object.entries(themes).map(([key, theme]) => ({
  value: key as ThemeType,
  label: theme.displayName,
  isDark: theme.isDark,
}));
