import type { ReactNode } from 'react'

export interface ArbitrageTopHeaderProps {
  searchQuery: string
  onSearchChange: (value: string) => void
  searchPlaceholder?: string
}

function IconButton({ label, children }: { label: string; children: ReactNode }) {
  return (
    <button type="button" className="arb-icon-btn" aria-label={label}>
      {children}
    </button>
  )
}

export function ArbitrageTopHeader({
  searchQuery,
  onSearchChange,
  searchPlaceholder = 'Search products…',
}: ArbitrageTopHeaderProps) {
  return (
    <header className="arb-top-header">
      <div className="arb-top-header__search-wrap">
        <span className="arb-top-header__search-icon" aria-hidden="true">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="11" cy="11" r="7" />
            <path d="M21 21l-4.35-4.35" />
          </svg>
        </span>
        <input
          type="search"
          className="arb-top-header__search"
          placeholder={searchPlaceholder}
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          autoComplete="off"
        />
      </div>
      <div className="arb-top-header__actions">
        <IconButton label="History">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
            <path d="M3 12a9 9 0 1 0 3-7.1" />
            <path d="M3 4v5h5" />
          </svg>
        </IconButton>
        <IconButton label="Notifications">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
            <path d="M18 8a6 6 0 10-12 0c0 7-3 7-3 7h18s-3 0-3-7" />
            <path d="M13.73 21a2 2 0 01-3.46 0" />
          </svg>
        </IconButton>
        <IconButton label="Settings">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
            <circle cx="12" cy="12" r="3" />
            <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
          </svg>
        </IconButton>
        <IconButton label="Profile">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
            <circle cx="12" cy="8" r="4" />
            <path d="M4 20c1.5-4 6-6 8-6s6.5 2 8 6" />
          </svg>
        </IconButton>
      </div>
    </header>
  )
}
