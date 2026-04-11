import { useCallback, useEffect, useState } from 'react'
import quiksaveLogo from '../assets/quiksave-logo-transparent.png'
import locationChevron from '../assets/location-chevron.svg'
import { useAppStore } from '../store/appStore'
import { logFrontendEvent } from '../lib/frontendLogger'
import type { LocationPayload } from '../services/api'
import { formatLocationHeaderLabel } from '../lib/locationDisplay'

export const AppHeader = () => {
  const lastLocation = useAppStore((s) => s.lastLocation)
  const setLastLocation = useAppStore((s) => s.setLastLocation)
  const lastLocationPayload = useAppStore((s) => s.lastLocationPayload)
  const setLastLocationPayload = useAppStore((s) => s.setLastLocationPayload)

  const [isLocationModalOpen, setIsLocationModalOpen] = useState(false)
  const [locationSearch, setLocationSearch] = useState('')
  const [isDetectingLocation, setIsDetectingLocation] = useState(false)

  const detectLocation = useCallback(async () => {
    setIsDetectingLocation(true)
    logFrontendEvent('location_detection_started')
    try {
      if (typeof navigator !== 'undefined' && navigator.geolocation) {
        const coords = await new Promise<GeolocationCoordinates>((resolve, reject) => {
          navigator.geolocation.getCurrentPosition(
            (pos) => resolve(pos.coords),
            (err) => reject(err),
            { enableHighAccuracy: true, timeout: 8000, maximumAge: 5 * 60 * 1000 },
          )
        })

        let city: string | undefined
        let pincode: string | undefined
        try {
          const rev = await fetch(
            `https://api.bigdatacloud.net/data/reverse-geocode-client?latitude=${coords.latitude}&longitude=${coords.longitude}&localityLanguage=en`,
          )
          if (rev.ok) {
            const data = await rev.json()
            city = data?.city || data?.locality || data?.principalSubdivision
            pincode = data?.postcode
          }
        } catch {
          // Reverse geocode can fail; coordinates are still useful.
        }

        const label = [city, pincode].filter(Boolean).join(', ') || 'Detected from your device'
        const payload: LocationPayload = {
          name: label,
          city,
          pincode,
          lat: coords.latitude,
          lng: coords.longitude,
          source: 'geolocation',
        }
        setLastLocation(label)
        setLastLocationPayload(payload)
        logFrontendEvent('location_detection_success', { source: 'geolocation', label, city, pincode })
        setIsDetectingLocation(false)
        return
      }
    } catch {
      logFrontendEvent('location_detection_error', { source: 'geolocation' })
    }

    const fallback = useAppStore.getState().lastLocation ?? 'Location unavailable'
    setLastLocation(fallback)
    logFrontendEvent('location_detection_fallback', { source: 'frontend_fallback', label: fallback })
    setIsDetectingLocation(false)
  }, [setLastLocation, setLastLocationPayload])

  useEffect(() => {
    void detectLocation()
    // Intentionally once on app load; Enable in modal calls detectLocation directly.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const locationButtonLabel =
    formatLocationHeaderLabel(lastLocation, lastLocationPayload) || 'Select Location'

  return (
    <>
      <header className="app-header">
        <div className="app-header-inner">
          <div className="input-logo-wrap">
            <img src={quiksaveLogo} alt="Quiksave" className="input-logo-img" />
          </div>
          <button
            type="button"
            className="input-location-button"
            aria-label={locationButtonLabel === 'Select Location' ? 'Select location' : `Location: ${locationButtonLabel}. Change location`}
            onClick={() => setIsLocationModalOpen(true)}
          >
            <span className="input-location-label" title={locationButtonLabel}>
              {locationButtonLabel}
            </span>
            <img src={locationChevron} alt="" className="input-location-caret-img" aria-hidden="true" />
          </button>
        </div>
        <div className="app-header-divider" aria-hidden="true" />
      </header>

      {isLocationModalOpen ? (
        <div
          className="location-modal-backdrop"
          onClick={() => setIsLocationModalOpen(false)}
          role="presentation"
        >
          <div
            className="location-modal"
            role="dialog"
            aria-modal="true"
            aria-label="Select your location"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="location-modal-header">
              <h2>
                <span className="location-title-pin" aria-hidden="true">
                  📍
                </span>
                Your Location
              </h2>
              <button
                type="button"
                className="location-modal-close"
                onClick={() => setIsLocationModalOpen(false)}
                aria-label="Close location modal"
              >
                ×
              </button>
            </div>

            <div className="location-modal-body">
              <div className="location-search-row">
                <span className="location-search-icon" aria-hidden="true">
                  🔍
                </span>
                <input
                  type="text"
                  value={locationSearch}
                  onChange={(e) => setLocationSearch(e.target.value)}
                  placeholder="Search a new address"
                  className="location-search-input"
                />
              </div>

              <div className="location-current-card">
                <div className="location-current-text">
                  <p className="location-current-title">Use My Current Location</p>
                  <p className="location-current-subtitle">
                    {isDetectingLocation
                      ? 'Detecting your location...'
                      : `Current: ${lastLocation || lastLocationPayload?.name || 'Unavailable'} `}
                    <span className="location-current-dot" aria-hidden="true" />
                  </p>
                </div>
                <button
                  type="button"
                  className="location-enable-button"
                  onClick={detectLocation}
                  disabled={isDetectingLocation}
                >
                  {isDetectingLocation ? 'Enabling...' : 'Enable'}
                </button>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </>
  )
}
