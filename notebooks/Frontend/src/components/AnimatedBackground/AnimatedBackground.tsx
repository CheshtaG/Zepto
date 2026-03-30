import './animated-bg.css'

export type AnimatedBackgroundProps = {
  intensity?: 'low' | 'medium'
  className?: string
}

export function AnimatedBackground({ intensity = 'low', className }: AnimatedBackgroundProps) {
  const opacity = intensity === 'medium' ? 0.2 : 0.15
  const lavenderOpacity = intensity === 'medium' ? 0.16 : 0.12

  return (
    <div
      className={['qs-bg-layer', className].filter(Boolean).join(' ')}
      aria-hidden="true"
    >
      <div className="qs-blob qs-blob-purple" style={{ opacity }} />
      <div
        className="qs-blob qs-blob-mint"
        style={{ opacity: Math.max(0, opacity - 0.03) }}
      />
      <div
        className="qs-blob qs-blob-purple2"
        style={{ opacity: lavenderOpacity }}
      />
    </div>
  )
}

