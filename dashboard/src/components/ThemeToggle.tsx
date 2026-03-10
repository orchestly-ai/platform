import React, { useState, useRef, useEffect } from 'react';
import { Sun, Moon, Monitor, ChevronDown, Sparkles } from 'lucide-react';
import { useTheme } from '../contexts/ThemeContext';
import { themeOptions } from '../utils/themes';

const themeIcons: Record<string, React.ReactNode> = {
  'light': <Sun className="w-4 h-4 text-yellow-500" />,
  'monokai-pro': <Sparkles className="w-4 h-4" style={{ color: '#fc9867' }} />,
  'dracula': <Sparkles className="w-4 h-4" style={{ color: '#bd93f9' }} />,
  'nord': <Sparkles className="w-4 h-4" style={{ color: '#88c0d0' }} />,
  'one-dark': <Sparkles className="w-4 h-4" style={{ color: '#61afef' }} />,
};

const ThemeToggle: React.FC = () => {
  const { themeName, setTheme, useSystemPreference, setUseSystemPreference } = useTheme();
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const currentThemeOption = themeOptions.find(t => t.value === themeName);

  const getIcon = () => {
    if (useSystemPreference) {
      return <Monitor className="w-4 h-4" style={{ color: 'var(--text-secondary)' }} />;
    }
    return themeIcons[themeName] || <Moon className="w-4 h-4" />;
  };

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-3 py-2 rounded-lg transition-colors hover:bg-gray-100 dark:hover:bg-gray-800"
        title="Select theme (Ctrl+Shift+T to cycle)"
        style={{ color: 'var(--text-primary)' }}
      >
        {getIcon()}
        <span className="text-sm hidden sm:inline">
          {useSystemPreference ? 'System' : currentThemeOption?.label}
        </span>
        <ChevronDown className="w-3 h-3" style={{ color: 'var(--text-secondary)' }} />

        {themeName === 'monokai-pro' && !useSystemPreference && (
          <div className="flex items-center gap-0.5 ml-1">
            <div className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ backgroundColor: 'var(--pink)' }} />
            <div className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ backgroundColor: 'var(--green)', animationDelay: '75ms' }} />
            <div className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ backgroundColor: 'var(--yellow)', animationDelay: '150ms' }} />
          </div>
        )}
      </button>

      {isOpen && (
        <div className="absolute right-0 top-full mt-1 py-1 rounded-lg shadow-lg z-50 min-w-[180px]"
             style={{ backgroundColor: 'var(--bg-primary)', border: '1px solid var(--border-primary)' }}>
          <button
            onClick={() => { setUseSystemPreference(true); setIsOpen(false); }}
            className="w-full px-3 py-2 text-left text-sm flex items-center gap-2 transition-colors"
            style={{
              color: 'var(--text-primary)',
              backgroundColor: useSystemPreference ? 'var(--bg-hover)' : 'transparent'
            }}
            onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--bg-hover)'}
            onMouseLeave={(e) => e.currentTarget.style.backgroundColor = useSystemPreference ? 'var(--bg-hover)' : 'transparent'}
          >
            <Monitor className="w-4 h-4" style={{ color: 'var(--text-secondary)' }} />
            <span>System</span>
            {useSystemPreference && <span className="ml-auto" style={{ color: 'var(--accent)' }}>✓</span>}
          </button>

          <div style={{ borderTop: '1px solid var(--border-primary)', margin: '4px 0' }} />

          {themeOptions.map((option) => (
            <button
              key={option.value}
              onClick={() => { setTheme(option.value); setIsOpen(false); }}
              className="w-full px-3 py-2 text-left text-sm flex items-center gap-2 transition-colors"
              style={{
                color: 'var(--text-primary)',
                backgroundColor: !useSystemPreference && themeName === option.value ? 'var(--bg-hover)' : 'transparent'
              }}
              onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--bg-hover)'}
              onMouseLeave={(e) => e.currentTarget.style.backgroundColor = !useSystemPreference && themeName === option.value ? 'var(--bg-hover)' : 'transparent'}
            >
              {themeIcons[option.value]}
              <span>{option.label}</span>
              {!useSystemPreference && themeName === option.value && (
                <span className="ml-auto" style={{ color: 'var(--accent)' }}>✓</span>
              )}
            </button>
          ))}

          <div style={{ borderTop: '1px solid var(--border-primary)', marginTop: '4px', paddingTop: '4px' }} className="px-3 py-1">
            <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
              <kbd className="px-1 py-0.5 rounded text-xs" style={{ backgroundColor: 'var(--bg-tertiary)' }}>Ctrl</kbd>
              {' + '}
              <kbd className="px-1 py-0.5 rounded text-xs" style={{ backgroundColor: 'var(--bg-tertiary)' }}>Shift</kbd>
              {' + '}
              <kbd className="px-1 py-0.5 rounded text-xs" style={{ backgroundColor: 'var(--bg-tertiary)' }}>T</kbd>
            </span>
          </div>
        </div>
      )}
    </div>
  );
};

export default ThemeToggle;
