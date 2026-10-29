import type { ReactNode } from 'react'
import { CircleCheck, CircleX, Clock, LoaderCircle } from 'lucide-react'
import PageHeader from '@/components/PageHeader'
import { Badge, SourceStatusBadge } from '@/components/badges'
import { DateTimeText } from '@/components/dates'
import { ErrorPanel, Forbidden, LoadingBlock, TableSkeleton } from '@/components/feedback'
import { getOpsStatus, type JobBrief, type OpsStatus } from '@/lib/api-governance'
import { humanize, sourceMethodLabel } from '@/lib/labels'
import { useApi } from '@/lib/useApi'
import { useAuth } from '@/store/auth'

const STORAGE_LABEL: Record<OpsStatus['storage_backend'], string> = {
  s3: 'Bucket S3 compatible',
  local: 'Disco local del servicio',
  invalid: 'Configuración incompleta',
}

// ── Diagrama de arquitectura ─────────────────────────────────────────────────
// SVG en línea con colores explícitos (fondo y trazos propios): se lee igual con tema claro u oscuro del sistema.

const INK = '#0F172A'
const INK_SOFT = '#334155'
const LINE = '#475569'
const BLUE = '#0F75BC'

const MODULES: { name: string; note: string }[] = [
  { name: 'Identidad y permisos', note: 'Sesión JWT · 5 roles' },
  { name: 'Catálogo', note: 'Productos y variantes' },
  { name: 'Oportunidades', note: 'Radar y búsqueda en fuentes' },
  { name: 'Documentos', note: 'Versiones, hash y visor' },
  { name: 'Requisitos', note: 'Matriz y evidencia' },
  { name: 'Revisión', note: 'Validación humana' },
  { name: 'Generación', note: 'Borradores y paquete ZIP' },
  { name: 'Auditoría', note: 'Bitácora con cadena SHA-256' },
  { name: 'Trabajos', note: '' },
]

function Architecture({ ops }: { ops: OpsStatus | undefined }) {
  const worker = ops === undefined ? null : ops.worker_alive
  const storage = ops ? STORAGE_LABEL[ops.storage_backend] : 'Almacenamiento de archivos'
  return (
    <div className="relative overflow-x-auto">
      <svg
        viewBox="0 0 1040 540"
        role="img"
        aria-labelledby="ti-title ti-desc"
        className="mx-auto block h-auto w-full min-w-[820px] max-w-[1040px] font-sans"
      >
        <title id="ti-title">Arquitectura del sistema</title>
        <desc id="ti-desc">
          El navegador llama a una API FastAPI que contiene los módulos de identidad, catálogo, oportunidades, documentos,
          requisitos, revisión, generación, auditoría y trabajos. La API guarda estados y relaciones en PostgreSQL y los
          archivos en un bucket o en disco local, y consulta fuentes oficiales desde el servidor. Planta y ERP son
          integraciones futuras, todavía no construidas.
        </desc>
        <defs>
          <marker id="ti-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
            <path d="M0 0 L10 5 L0 10 z" fill={LINE} />
          </marker>
        </defs>
        <rect x="0.5" y="0.5" width="1039" height="539" rx="10" fill="#F8FAFC" stroke="#CBD5E1" />

        {/* Navegador */}
        <rect x="355" y="20" width="330" height="52" rx="8" fill="#FFFFFF" stroke={BLUE} strokeWidth="1.5" />
        <text x="520" y="42" textAnchor="middle" fontSize="14" fontWeight="600" fill={INK}>Navegador</text>
        <text x="520" y="60" textAnchor="middle" fontSize="11.5" fill={INK_SOFT}>React · TypeScript · Tailwind</text>
        <line x1="520" y1="72" x2="520" y2="106" stroke={LINE} strokeWidth="1.5" markerEnd="url(#ti-arrow)" />
        <text x="530" y="94" fontSize="11" fill={INK_SOFT}>HTTPS · JSON</text>

        {/* API */}
        <rect x="30" y="108" width="770" height="256" rx="12" fill="#EEF6FC" stroke={BLUE} strokeWidth="1.5" />
        <text x="48" y="132" fontSize="14" fontWeight="600" fill={INK}>API · FastAPI (monolito modular)</text>
        <text x="48" y="148" fontSize="11" fill={INK_SOFT}>Valida permisos en cada petición, guarda estados y registra cada cambio sensible en la bitácora.</text>
        {MODULES.map((m, i) => {
          const x = 48 + (i % 3) * 248
          const y = 162 + Math.floor(i / 3) * 64
          const isJobs = m.name === 'Trabajos'
          return (
            <g key={m.name}>
              <rect x={x} y={y} width="232" height="52" rx="7" fill="#FFFFFF" stroke="#94A3B8" />
              <text x={x + 14} y={y + 22} fontSize="13" fontWeight="600" fill={INK}>{m.name}</text>
              {isJobs ? (
                <text x={x + 14} y={y + 40} fontSize="11.5" fontWeight="600" fill={worker === null ? INK_SOFT : worker ? '#166534' : '#991B1B'}>
                  {worker === null ? 'Worker: sin dato' : worker ? '✓ Worker activo' : '✕ Worker detenido'}
                </text>
              ) : (
                <text x={x + 14} y={y + 40} fontSize="11.5" fill={INK_SOFT}>{m.note}</text>
              )}
            </g>
          )
        })}

        {/* Fuentes oficiales: se consultan desde el servidor */}
        <rect x="850" y="162" width="170" height="72" rx="8" fill="#FFFFFF" stroke="#94A3B8" />
        <text x="865" y="184" fontSize="13" fontWeight="600" fill={INK}>Fuentes oficiales</text>
        <text x="865" y="202" fontSize="11" fill={INK_SOFT}>SIDOF · Compras MX · IMSS</text>
        <text x="865" y="218" fontSize="11" fill={INK_SOFT}>consulta desde el servidor</text>
        <line x1="776" y1="188" x2="848" y2="198" stroke={LINE} strokeWidth="1.5" markerEnd="url(#ti-arrow)" />

        {/* Integraciones futuras: línea punteada, sin acciones */}
        <rect x="850" y="262" width="170" height="46" rx="8" fill="#F8FAFC" stroke={LINE} strokeWidth="1.5" strokeDasharray="6 4" />
        <text x="865" y="282" fontSize="12.5" fontWeight="600" fill={INK}>
          <tspan>Planta </tspan>
          <tspan x="865" dy="16" fontWeight="500" fontSize="11.5" fill={INK_SOFT}>(integración futura)</tspan>
        </text>
        <line x1="800" y1="285" x2="850" y2="285" stroke={LINE} strokeWidth="1.5" strokeDasharray="6 4" />
        <rect x="850" y="322" width="170" height="46" rx="8" fill="#F8FAFC" stroke={LINE} strokeWidth="1.5" strokeDasharray="6 4" />
        <text x="865" y="342" fontSize="12.5" fontWeight="600" fill={INK}>
          <tspan>ERP </tspan>
          <tspan x="865" dy="16" fontWeight="500" fontSize="11.5" fill={INK_SOFT}>(integración futura)</tspan>
        </text>
        <line x1="800" y1="345" x2="850" y2="345" stroke={LINE} strokeWidth="1.5" strokeDasharray="6 4" />

        {/* PostgreSQL */}
        <line x1="230" y1="364" x2="230" y2="410" stroke={LINE} strokeWidth="1.5" markerEnd="url(#ti-arrow)" />
        <text x="240" y="392" fontSize="11" fill={INK_SOFT}>SQL</text>
        <path d="M130 428 v58 a100 15 0 0 0 200 0 v-58" fill="#FFFFFF" stroke={BLUE} strokeWidth="1.5" />
        <ellipse cx="230" cy="428" rx="100" ry="15" fill="#FFFFFF" stroke={BLUE} strokeWidth="1.5" />
        <text x="230" y="458" textAnchor="middle" fontSize="13" fontWeight="600" fill={INK}>PostgreSQL</text>
        <text x="230" y="475" textAnchor="middle" fontSize="11" fill={INK_SOFT}>Estados, relaciones y bitácora</text>

        {/* Bucket */}
        <line x1="570" y1="364" x2="570" y2="410" stroke={LINE} strokeWidth="1.5" markerEnd="url(#ti-arrow)" />
        <text x="580" y="392" fontSize="11" fill={INK_SOFT}>archivos</text>
        <path d="M460 414 h220 l-18 78 h-184 z" fill="#FFFFFF" stroke={BLUE} strokeWidth="1.5" strokeLinejoin="round" />
        <text x="570" y="448" textAnchor="middle" fontSize="13" fontWeight="600" fill={INK}>Bucket de archivos</text>
        <text x="570" y="466" textAnchor="middle" fontSize="11.5" fill={INK_SOFT}>{storage}</text>

        {/* Leyenda */}
        <line x1="760" y1="500" x2="800" y2="500" stroke={LINE} strokeWidth="1.5" />
        <text x="808" y="504" fontSize="11" fill={INK_SOFT}>Existe hoy</text>
        <line x1="760" y1="520" x2="800" y2="520" stroke={LINE} strokeWidth="1.5" strokeDasharray="6 4" />
        <text x="808" y="524" fontSize="11" fill={INK_SOFT}>Integración futura, no construida</text>
      </svg>
    </div>
  )
}

// ── Estado operativo ─────────────────────────────────────────────────────────

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className="mt-0.5 text-sm font-medium text-slate-900">{children}</dd>
    </div>
  )
}

function Facts({ ops }: { ops: OpsStatus }) {
  const run = ops.demo_run
  return (
    <section aria-labelledby="despliegue" className="card">
      <h2 id="despliegue" className="border-b border-slate-200 px-4 py-3 font-semibold text-slate-900">
        Despliegue
      </h2>
      <dl className="grid gap-x-6 gap-y-4 px-4 py-4 sm:grid-cols-2 lg:grid-cols-3">
        <Fact label="Versión desplegada">
          <code className="rounded bg-slate-100 px-1.5 py-0.5 tabular-nums">{ops.version}</code>
          {ops.version === 'local' && <span className="ml-2 text-xs font-normal text-slate-600">ejecución local, sin commit</span>}
        </Fact>
        <Fact label="Revisión de la base de datos">
          {ops.alembic_head ? (
            <code className="rounded bg-slate-100 px-1.5 py-0.5 tabular-nums">{ops.alembic_head}</code>
          ) : (
            <span className="font-normal text-slate-600">Sin dato: el esquema no se creó con Alembic</span>
          )}
        </Fact>
        <Fact label="Almacenamiento de archivos">
          {STORAGE_LABEL[ops.storage_backend]}
          {ops.storage_backend === 'local' && (
            <span className="mt-1 block text-xs font-normal text-slate-600">
              Sin bucket configurado, los archivos cargados viven en el disco del servicio y se pierden al redesplegar.
            </span>
          )}
          {ops.storage_error && <span className="mt-1 block text-xs font-normal text-red-800">{ops.storage_error}</span>}
        </Fact>
        <Fact label="Worker de trabajos">
          {ops.worker_alive ? (
            <span className="inline-flex items-center gap-1.5 text-emerald-800">
              <CircleCheck aria-hidden="true" className="h-4 w-4" />
              Activo
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 text-red-800">
              <CircleX aria-hidden="true" className="h-4 w-4" />
              Detenido
            </span>
          )}
          {!ops.worker_alive && (
            <span className="mt-1 block text-xs font-normal text-slate-600">
              Los trabajos en cola no avanzan hasta que el servicio arranque con el worker.
            </span>
          )}
        </Fact>
        <Fact label="Corrida demo actual">
          {run ? (
            <>
              <DateTimeText value={run.started_at} />
              {run.actor && <span className="block text-xs font-normal text-slate-600">Reinició: {run.actor.full_name}</span>}
            </>
          ) : (
            <span className="font-normal text-slate-600">Sin corridas</span>
          )}
        </Fact>
      </dl>
    </section>
  )
}

function Sources({ ops }: { ops: OpsStatus }) {
  return (
    <section aria-labelledby="salud-fuentes" className="card overflow-hidden">
      <div className="border-b border-slate-200 px-4 py-3">
        <h2 id="salud-fuentes" className="font-semibold text-slate-900">
          Salud de las fuentes
        </h2>
        <p className="mt-0.5 text-xs text-slate-600">
          Una fuente no probada, bloqueada o inaccesible no significa que no existan procedimientos.
        </p>
      </div>
      <div className="relative overflow-x-auto">
        <table className="table-base table-compact min-w-[760px]">
          <caption className="sr-only">Estado de cada fuente</caption>
          <thead>
            <tr>
              <th scope="col">Fuente</th>
              <th scope="col">Estado</th>
              <th scope="col">Método</th>
              <th scope="col">Última consulta</th>
              <th scope="col">Último error</th>
            </tr>
          </thead>
          <tbody>
            {ops.sources.map((s) => (
              <tr key={s.id}>
                <td className="min-w-[180px]">
                  <div className="font-medium text-slate-900">{s.name}</div>
                  <div className="text-xs text-slate-500">{s.key}</div>
                </td>
                <td>
                  <SourceStatusBadge status={s.status} />
                </td>
                <td className="whitespace-nowrap">{sourceMethodLabel(s.method)}</td>
                <td className="whitespace-nowrap">
                  <DateTimeText value={s.last_checked_at} empty="Nunca consultada" />
                </td>
                <td className="min-w-[200px] text-xs">
                  {s.last_error ? <span className="text-red-800">{s.last_error}</span> : <span className="muted">Sin errores registrados</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

const JOB_STATUS: Record<string, { label: string; icon: typeof Clock; className: string }> = {
  queued: { label: 'En cola', icon: Clock, className: 'border-amber-300 bg-amber-50 text-amber-900' },
  running: { label: 'En ejecución', icon: LoaderCircle, className: 'border-sky-300 bg-sky-50 text-sky-800' },
  done: { label: 'Terminado', icon: CircleCheck, className: 'border-emerald-300 bg-emerald-50 text-emerald-800' },
  failed: { label: 'Falló', icon: CircleX, className: 'border-red-300 bg-red-50 text-red-800' },
}

function JobStatus({ status }: { status: string }) {
  const s = JOB_STATUS[status]
  if (!s) return <Badge tone={{ icon: Clock, className: 'border-slate-300 bg-white text-slate-700' }}>{humanize(status)}</Badge>
  return <Badge tone={s}>{s.label}</Badge>
}

function Jobs({ jobs }: { jobs: JobBrief[] }) {
  return (
    <section aria-labelledby="trabajos" className="card overflow-hidden">
      <div className="border-b border-slate-200 px-4 py-3">
        <h2 id="trabajos" className="font-semibold text-slate-900">
          Trabajos recientes
        </h2>
        <p className="mt-0.5 text-xs text-slate-600">Los últimos 20 de la cola. Un trabajo fallido conserva el motivo.</p>
      </div>
      {jobs.length === 0 ? (
        <p className="px-4 py-5 text-sm text-slate-600">Todavía no se ha ejecutado ningún trabajo.</p>
      ) : (
        <div className="relative overflow-x-auto">
          <table className="table-base table-compact min-w-[820px]">
            <caption className="sr-only">Trabajos recientes de la cola</caption>
            <thead>
              <tr>
                <th scope="col">Tipo</th>
                <th scope="col">Estado</th>
                <th scope="col">Avance</th>
                <th scope="col">Detalle</th>
                <th scope="col">Creado</th>
                <th scope="col">Terminó</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((j) => (
                <tr key={j.id}>
                  <td className="whitespace-nowrap">
                    <code className="text-xs text-slate-800">{j.kind}</code>
                  </td>
                  <td>
                    <JobStatus status={j.status} />
                  </td>
                  <td className="tabular-nums">{j.progress}%</td>
                  <td className="min-w-[220px] text-xs">
                    {j.error ? (
                      <span className="text-red-800">{j.error}</span>
                    ) : j.message ? (
                      <span className="text-slate-700">{j.message}</span>
                    ) : (
                      <span className="muted">—</span>
                    )}
                  </td>
                  <td className="whitespace-nowrap">
                    <DateTimeText value={j.created_at} />
                  </td>
                  <td className="whitespace-nowrap">
                    <DateTimeText value={j.finished_at} empty="—" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

export default function TI() {
  const permissions = useAuth((s) => s.me?.permissions ?? [])
  const allowed = permissions.includes('source.manage') || permissions.includes('audit.read')
  const ops = useApi(getOpsStatus, [], allowed)

  if (!allowed) {
    return (
      <div className="space-y-6">
        <PageHeader title="TI · Arquitectura y operación" />
        <Forbidden permission="source.manage" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="TI · Arquitectura y operación"
        description="Cómo está armado el sistema y qué está corriendo ahora. Lo marcado como futuro no está construido."
      />
      <section aria-labelledby="arquitectura" className="card">
        <h2 id="arquitectura" className="border-b border-slate-200 px-4 py-3 font-semibold text-slate-900">
          Arquitectura
        </h2>
        <div className="px-2 py-4 sm:px-4">
          <Architecture ops={ops.data} />
        </div>
      </section>
      {ops.error && <ErrorPanel error={ops.error} onRetry={ops.reload} />}
      {!ops.data && !ops.error && (
        <>
          <LoadingBlock label="Leyendo el estado del sistema…" />
          <TableSkeleton rows={3} cols={5} />
        </>
      )}
      {ops.data && (
        <>
          <Facts ops={ops.data} />
          <Sources ops={ops.data} />
          <Jobs jobs={ops.data.jobs} />
        </>
      )}
    </div>
  )
}
