interface SpinnerProps {
  size?: number;
}

export function Spinner({ size = 32 }: SpinnerProps) {
  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: '50%',
        border: '3px solid #e5e7eb',
        borderTopColor: '#3b82d4',
        animation: 'spin 0.7s linear infinite',
      }}
    />
  );
}
