import { DotLottie } from '@lottiefiles/dotlottie-web'
import { useEffect, useRef, type CSSProperties } from 'react'
import loadingSrc from '../../Images/Loading Dots Blue.lottie?url'

type Props = {
  className?: string
  /** Layout box in CSS px (flex uses this; does not grow the parent when `visualScale` is used). */
  width?: number
  height?: number
  /** >1 draws larger on screen via transform; layout stays `width`×`height`. Origin: left center. */
  visualScale?: number
  /** Extra horizontal nudge in px (negative = further left), added after auto centering compensation. */
  nudgeX?: number
  /** Horizontal alignment of the canvas inside the layout box (`end` = right, e.g. under BEST PRICE FOUND). */
  layoutAlign?: 'start' | 'end'
}

/**
 * Blue dots loading animation from `Frontend/Images/Loading Dots Blue.lottie`.
 * Uses `@lottiefiles/dotlottie-web` (canvas) instead of the React wrapper so Vite
 * resolves a single, stable ESM entry.
 */
export function LoadingDotsBlue({
  className,
  width = 82,
  height = 38,
  visualScale = 1,
  nudgeX = 0,
  layoutAlign = 'start',
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const dpr = Math.min(window.devicePixelRatio || 1, 2)
    canvas.width = Math.round(width * dpr)
    canvas.height = Math.round(height * dpr)
    canvas.style.width = `${width}px`
    canvas.style.height = `${height}px`

    const player = new DotLottie({
      canvas,
      src: loadingSrc,
      loop: true,
      autoplay: true,
      renderConfig: { autoResize: true },
    })
    return () => {
      try {
        player.destroy()
      } catch {
        /* load may still be in flight */
      }
    }
  }, [loadingSrc, width, height])

  const outerStyle: CSSProperties = {
    position: 'relative',
    width,
    height,
    minWidth: width,
    minHeight: height,
    flexShrink: 0,
    display: 'flex',
    alignItems: 'center',
    justifyContent: layoutAlign === 'end' ? 'flex-end' : 'flex-start',
  }

  const scaled = visualScale > 1
  /** Artwork is usually centered in the canvas; scaling from the left shifts the cluster right — pull back. */
  const centerCompensation =
    scaled ? -Math.round((width / 2) * (visualScale - 1)) : 0
  const tx = centerCompensation + nudgeX

  const canvasBlock = (
    <canvas ref={canvasRef} style={{ display: 'block', width: '100%', height: '100%' }} />
  )

  return (
    <div className={className} style={outerStyle} aria-hidden>
      {scaled ? (
        <div
          style={{
            position: 'absolute',
            top: '50%',
            width,
            height,
            left: layoutAlign === 'end' ? 'auto' : 0,
            right: layoutAlign === 'end' ? 0 : 'auto',
            transform: `translate(${layoutAlign === 'end' ? -tx : tx}px, -50%) scale(${visualScale})`,
            transformOrigin: layoutAlign === 'end' ? 'right center' : 'left center',
            pointerEvents: 'none',
          }}
        >
          {canvasBlock}
        </div>
      ) : (
        canvasBlock
      )}
    </div>
  )
}
