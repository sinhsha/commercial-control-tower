import { type ReactNode } from 'react';

interface SectionCardProps {
  title: string;
  children: ReactNode;
  action?: ReactNode;
}

export function SectionCard({ title, children, action }: SectionCardProps) {
  return (
    <div
      style={{
        background: '#ffffff',
        border: '1px solid #e5e7eb',
        borderRadius: 8,
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '14px 20px',
          borderBottom: '1px solid #e5e7eb',
          background: '#f7f8fa',
        }}
      >
        <span
          style={{
            fontSize: 13,
            fontWeight: 600,
            color: '#1f2328',
            letterSpacing: '0.01em',
          }}
        >
          {title}
        </span>
        {action}
      </div>
      <div style={{ padding: '16px 20px' }}>{children}</div>
    </div>
  );
}
