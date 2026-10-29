import { useState } from 'react'
import { ImageOff, TriangleAlert } from 'lucide-react'
import { Badge, ReviewStatusBadge } from '@/components/badges'

/**
 * Imagen remota del sitio de Dipromedic. Carga diferida y sin enviar el origen (`no-referrer`);
 * si falla, muestra un ícono en su lugar.
 */
export function ProductImage({ src, alt, className = '' }: { src: string | undefined; alt: string; className?: string }) {
  const [failed, setFailed] = useState(false)
  if (!src || failed) {
    return (
      <div
        role="img"
        aria-label={src ? 'La imagen no se pudo cargar' : 'Sin imagen publicada'}
        className={`flex items-center justify-center bg-slate-100 text-slate-400 ${className}`}
      >
        <ImageOff aria-hidden="true" className="h-8 w-8" strokeWidth={1.5} />
      </div>
    )
  }
  return (
    <img
      src={src}
      alt={alt}
      loading="lazy"
      decoding="async"
      referrerPolicy="no-referrer"
      onError={() => setFailed(true)}
      className={`bg-white object-contain ${className}`}
    />
  )
}

/** «Por revisar» (la página de origen tiene inconsistencias) destaca en ámbar; el resto usa la insignia común. */
export function CatalogReviewBadge({ status }: { status: string }) {
  if (status !== 'por_revisar') return <ReviewStatusBadge status={status} />
  return (
    <Badge tone={{ icon: TriangleAlert, className: 'border-amber-300 bg-amber-50 text-amber-900' }}>Por revisar</Badge>
  )
}
