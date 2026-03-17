import { KeyboardEvent } from 'react'

interface Props {
  value: string
  onChange: (value: string) => void
}

export const ExtraItemsInput = ({ value, onChange }: Props) => {
  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      // Wire this to extend the comparison job in a follow-up iteration.
    }
  }

  return (
    <div>
      <p className="landing-subtitle" style={{ marginBottom: 8 }}>
        Add more items to compare:
      </p>
      <textarea
        className="landing-textarea"
        style={{ width: '100%', height: '120px' }}
        placeholder="Type new items here…"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
      />
    </div>
  )
}

