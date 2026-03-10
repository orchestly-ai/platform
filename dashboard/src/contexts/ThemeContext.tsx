import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { themes, themeOptions } from '../utils/themes';
import type { ThemeType, Theme } from '../utils/themes';

const STORAGE_KEY = 'orchestration-theme';
const SYSTEM_PREFERENCE_KEY = 'orchestration-theme-use-system';

interface ThemeContextType {
  theme: Theme;
  themeName: ThemeType;
  themeType: ThemeType; // Alias for backward compatibility
  useSystemPreference: boolean;
  toggleTheme: () => void;
  cycleTheme: () => void;
  setTheme: (theme: ThemeType) => void;
  setUseSystemPreference: (use: boolean) => void;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export const useTheme = () => {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within ThemeProvider');
  }
  return context;
};

const getSystemPreference = (): 'light' | 'monokai-pro' => {
  if (typeof window !== 'undefined' && window.matchMedia) {
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'monokai-pro' : 'light';
  }
  return 'light';
};

const getInitialTheme = (): ThemeType => {
  if (typeof window === 'undefined') return 'light';
  const useSystem = localStorage.getItem(SYSTEM_PREFERENCE_KEY) === 'true';
  if (useSystem) return getSystemPreference();
  const saved = localStorage.getItem(STORAGE_KEY) as ThemeType;
  return saved && saved in themes ? saved : 'light';
};

const getInitialUseSystem = (): boolean => {
  if (typeof window === 'undefined') return false;
  return localStorage.getItem(SYSTEM_PREFERENCE_KEY) === 'true';
};

interface ThemeProviderProps {
  children: ReactNode;
}

export const ThemeProvider: React.FC<ThemeProviderProps> = ({ children }) => {
  const [themeName, setThemeName] = useState<ThemeType>(getInitialTheme);
  const [useSystemPreference, setUseSystemPref] = useState<boolean>(getInitialUseSystem);

  const theme = themes[themeName];

  const applyTheme = useCallback((currentTheme: Theme, currentThemeName: ThemeType) => {
    const root = document.documentElement;
    root.style.setProperty('--bg-primary', currentTheme.colors.bgPrimary);
    root.style.setProperty('--bg-secondary', currentTheme.colors.bgSecondary);
    root.style.setProperty('--bg-tertiary', currentTheme.colors.bgTertiary);
    root.style.setProperty('--bg-hover', currentTheme.colors.bgHover);
    root.style.setProperty('--bg-active', currentTheme.colors.bgActive);
    root.style.setProperty('--text-primary', currentTheme.colors.textPrimary);
    root.style.setProperty('--text-secondary', currentTheme.colors.textSecondary);
    root.style.setProperty('--text-tertiary', currentTheme.colors.textTertiary);
    root.style.setProperty('--text-inverse', currentTheme.colors.textInverse);
    root.style.setProperty('--border-primary', currentTheme.colors.borderPrimary);
    root.style.setProperty('--border-secondary', currentTheme.colors.borderSecondary);
    root.style.setProperty('--accent', currentTheme.colors.accent);
    root.style.setProperty('--accent-hover', currentTheme.colors.accentHover);
    root.style.setProperty('--success', currentTheme.colors.success);
    root.style.setProperty('--warning', currentTheme.colors.warning);
    root.style.setProperty('--error', currentTheme.colors.error);
    root.style.setProperty('--info', currentTheme.colors.info);
    root.style.setProperty('--pink', currentTheme.colors.pink);
    root.style.setProperty('--green', currentTheme.colors.green);
    root.style.setProperty('--yellow', currentTheme.colors.yellow);
    root.style.setProperty('--orange', currentTheme.colors.orange);
    root.style.setProperty('--purple', currentTheme.colors.purple);
    root.style.setProperty('--cyan', currentTheme.colors.cyan);
    root.style.setProperty('--red', currentTheme.colors.red);
    root.style.setProperty('--shadow-sm', currentTheme.shadows.sm);
    root.style.setProperty('--shadow-md', currentTheme.shadows.md);
    root.style.setProperty('--shadow-lg', currentTheme.shadows.lg);
    // Apply theme class and data-theme to both html and body for CSS selector compatibility
    const themeClass = currentTheme.isDark ? 'theme-dark' : 'theme-light';
    root.className = themeClass;
    root.setAttribute('data-theme', currentThemeName);
    document.body.className = themeClass;
    document.body.setAttribute('data-theme', currentThemeName);
  }, []);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, themeName);
    applyTheme(theme, themeName);
  }, [themeName, theme, applyTheme]);

  useEffect(() => {
    if (!useSystemPreference) return;
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const handleChange = (e: MediaQueryListEvent) => {
      setThemeName(e.matches ? 'monokai-pro' : 'light');
    };
    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, [useSystemPreference]);

  useEffect(() => {
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === STORAGE_KEY && e.newValue && e.newValue in themes) {
        setThemeName(e.newValue as ThemeType);
      }
      if (e.key === SYSTEM_PREFERENCE_KEY) {
        setUseSystemPref(e.newValue === 'true');
        if (e.newValue === 'true') setThemeName(getSystemPreference());
      }
    };
    window.addEventListener('storage', handleStorageChange);
    return () => window.removeEventListener('storage', handleStorageChange);
  }, []);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.shiftKey && e.key === 'T') {
        e.preventDefault();
        cycleTheme();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [themeName]);

  const toggleTheme = useCallback(() => {
    setUseSystemPref(false);
    localStorage.setItem(SYSTEM_PREFERENCE_KEY, 'false');
    setThemeName(prev => prev === 'light' ? 'monokai-pro' : 'light');
  }, []);

  const cycleTheme = useCallback(() => {
    setUseSystemPref(false);
    localStorage.setItem(SYSTEM_PREFERENCE_KEY, 'false');
    const themeKeys = Object.keys(themes) as ThemeType[];
    const currentIndex = themeKeys.indexOf(themeName);
    const nextIndex = (currentIndex + 1) % themeKeys.length;
    setThemeName(themeKeys[nextIndex]);
  }, [themeName]);

  const setTheme = useCallback((newTheme: ThemeType) => {
    setUseSystemPref(false);
    localStorage.setItem(SYSTEM_PREFERENCE_KEY, 'false');
    setThemeName(newTheme);
  }, []);

  const setUseSystemPreference = useCallback((use: boolean) => {
    setUseSystemPref(use);
    localStorage.setItem(SYSTEM_PREFERENCE_KEY, String(use));
    if (use) setThemeName(getSystemPreference());
  }, []);

  return (
    <ThemeContext.Provider value={{
      theme, themeName, themeType: themeName, useSystemPreference,
      toggleTheme, cycleTheme, setTheme, setUseSystemPreference
    }}>
      {children}
    </ThemeContext.Provider>
  );
};

export { themeOptions };
