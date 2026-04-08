import './App.css'
import { AppRouter } from './app/AppRouter'
import { useAppStore } from './store/appStore'
import { ErrorBoundary } from './app/ErrorBoundary'
import { AppHeader } from './components/AppHeader'

function App() {
  const { toast, setToast } = useAppStore()

  return (
    <ErrorBoundary>
      <AppHeader />
      <div className="app-body-with-header">
        <AppRouter />
      </div>
      {toast && (
        <div className="toast" role="status">
          <span>{toast.kind === 'error' ? '⚠️' : 'ℹ️'}</span>
          <span>{toast.message}</span>
          <button
            type="button"
            className="btn-icon"
            onClick={() => setToast(undefined)}
            aria-label="Dismiss"
          >
            ✕
          </button>
        </div>
      )}
    </ErrorBoundary>
  )
}

export default App
