export interface BottomOptimizeButtonProps {
  onClick?: () => void
}

export function BottomOptimizeButton({ onClick }: BottomOptimizeButtonProps) {
  return (
    <div className="arb-bottom-cta-wrap">
      <button type="button" className="arb-bottom-cta" onClick={onClick}>
        <span className="arb-bottom-cta__icon" aria-hidden="true">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.55">
            <path d="M12 3v2M5.6 5.6l1.4 1.4M3 12h2M5.6 18.4l1.4-1.4M12 21v-2M18.4 18.4l-1.4-1.4M21 12h-2M18.4 5.6l-1.4 1.4" />
            <circle cx="12" cy="12" r="3.2" />
            <path
              d="M19 2l.4 1.2 1.2.4-1.2.4L19 5l-.4-1.2-1.2-.4 1.2-.4L19 2z"
              fill="currentColor"
              stroke="none"
              opacity="0.85"
            />
          </svg>
        </span>
        Optimize for Lowest Delivery Fee
      </button>
    </div>
  )
}
