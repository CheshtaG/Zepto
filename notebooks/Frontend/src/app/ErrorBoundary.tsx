import { Component, ErrorInfo, ReactNode } from 'react'
import { logger } from '../lib/logger'

interface Props {
  children: ReactNode
}

interface State {
  hasError: boolean
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false }

  static getDerivedStateFromError() {
    return { hasError: true }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    logger.error('React error boundary caught error', { error: error.message, info })
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="simple-page">
          <div className="landing-content">
            <h1>Something went wrong</h1>
            <p className="landing-subtitle">
              Please refresh the page or start a new comparison.
            </p>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}

