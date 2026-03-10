import { Lock } from 'lucide-react';

interface UpgradeBannerProps {
  feature: string;
}

export function UpgradeBanner({ feature }: UpgradeBannerProps) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '12px',
        padding: '16px 20px',
        borderRadius: '8px',
        backgroundColor: 'var(--color-warning-bg, #fff8e1)',
        border: '1px solid var(--color-warning-border, #ffe082)',
        color: 'var(--color-warning-text, #6d4c00)',
        margin: '16px 0',
      }}
    >
      <Lock size={18} />
      <span>
        <strong>{feature}</strong> requires a paid plan.{' '}
        <a
          href="/settings?tab=billing"
          style={{
            color: 'var(--color-primary, #1976d2)',
            textDecoration: 'underline',
            fontWeight: 600,
          }}
        >
          Upgrade
        </a>
      </span>
    </div>
  );
}
