interface BadgeProps {
  children: string;
  variant?: 'green' | 'yellow' | 'red' | 'blue' | 'purple' | 'gray';
}

const variants = {
  green:  { bg: '#dcfce7', color: '#15803d' },
  yellow: { bg: '#fef9c3', color: '#92400e' },
  red:    { bg: '#fee2e2', color: '#b91c1c' },
  blue:   { bg: '#dbeafe', color: '#1d4ed8' },
  purple: { bg: '#eef2ff', color: '#4338ca' },
  gray:   { bg: '#f3f4f6', color: '#4b5563' },
} as const;

export function Badge({ children, variant = 'gray' }: BadgeProps) {
  const { bg, color } = variants[variant];
  return (
    <span
      style={{
        display: 'inline-block',
        padding: '2px 8px',
        borderRadius: 999,
        background: bg,
        color,
        fontSize: 11,
        fontWeight: 600,
        letterSpacing: '0.04em',
      }}
    >
      {children}
    </span>
  );
}
