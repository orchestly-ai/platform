/**
 * Brand Icons for Integrations
 * Maps integration slugs to their official brand SVG icons and colors.
 * Uses react-icons/si (SimpleIcons) where available, custom SVGs otherwise.
 */

import React from 'react';
import {
  SiOpenai,
  SiAnthropic,
  SiGooglegemini,
  SiSlack,
  SiSalesforce,
  SiGithub,
  SiStripe,
  SiZendesk,
  SiGoogledrive,
  SiMailchimp,
  SiJira,
} from 'react-icons/si';
import { Cpu, Server } from 'lucide-react';

/* ─── Custom icons not in react-icons ─── */

function DeepSeekIcon({ size = 22 }: { size?: number }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" width={size} height={size}>
      <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 15.5v-3.07c-1.41-.45-2.53-1.53-3.03-2.93H5.5v-1h2.47c.5-1.4 1.62-2.48 3.03-2.93V4.5h1v3.07c1.41.45 2.53 1.53 3.03 2.93H17.5v1h-2.47c-.5 1.4-1.62 2.48-3.03 2.93V17.5h-1z" />
    </svg>
  );
}

function GroqIcon({ size = 22 }: { size?: number }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" width={size} height={size}>
      <path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm0 3a7 7 0 1 1 0 14 7 7 0 0 1 0-14zm0 2.5a4.5 4.5 0 1 0 0 9 4.5 4.5 0 0 0 0-9zm0 2a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5z" />
    </svg>
  );
}

/* ─── Brand registry ─── */

interface BrandInfo {
  icon: React.ComponentType<{ size?: number; className?: string; style?: React.CSSProperties }>;
  color: string;
}

const brandRegistry: Record<string, BrandInfo> = {
  // AI/LLM Providers
  openai: { icon: SiOpenai, color: '#10a37f' },
  anthropic: { icon: SiAnthropic, color: '#d4a27f' },
  'google-ai': { icon: SiGooglegemini, color: '#8e75b2' },
  deepseek: { icon: DeepSeekIcon, color: '#4d6bfe' },
  groq: { icon: GroqIcon, color: '#f55036' },

  // Communication
  slack: { icon: SiSlack, color: '#e01e5a' },

  // Developer Tools
  github: { icon: SiGithub, color: '#f0f0f0' },

  // Cloud Storage
  'google-drive': { icon: SiGoogledrive, color: '#4285f4' },

  // CRM
  salesforce: { icon: SiSalesforce, color: '#00a1e0' },

  // Finance
  stripe: { icon: SiStripe, color: '#635bff' },

  // Marketing
  mailchimp: { icon: SiMailchimp, color: '#ffe01b' },

  // Project Management
  jira: { icon: SiJira, color: '#0052cc' },

  // Support
  zendesk: { icon: SiZendesk, color: '#17494d' },
};

export function getBrandInfo(slug: string): BrandInfo | null {
  return brandRegistry[slug] || null;
}

export function BrandIcon({
  slug,
  size = 22,
  fallbackIcon: FallbackIcon,
  fallbackColor,
}: {
  slug: string;
  size?: number;
  fallbackIcon?: React.ComponentType<{ size?: number; className?: string; style?: React.CSSProperties }>;
  fallbackColor?: string;
}) {
  const brand = brandRegistry[slug];

  if (brand) {
    const Icon = brand.icon;
    return (
      <div
        className="flex items-center justify-center"
        style={{ color: brand.color }}
      >
        <Icon size={size} />
      </div>
    );
  }

  // Fallback to category icon
  if (FallbackIcon) {
    return (
      <div className="flex items-center justify-center" style={{ color: fallbackColor || 'var(--accent)' }}>
        <FallbackIcon size={size} />
      </div>
    );
  }

  return (
    <div className="flex items-center justify-center" style={{ color: 'var(--accent)' }}>
      <Cpu size={size} />
    </div>
  );
}
