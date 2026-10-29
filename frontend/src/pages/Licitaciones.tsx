import { FormEvent, useEffect, useState } from 'react'
import {
  api,
  errorMessage,
  ESTATUS_LABEL,
  TIPO_LABEL,
  type Estatus,
  type Licitacion,
  type Tipo,
} from '@/lib/api'
import StatusBadge from '@/components/StatusBadge'

const money = new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN', maximumFractionDigits: 0 })
const dateFmt = new Intl.DateTimeFormat('es-MX', { dateStyle: 'medium', timeStyle: 'short' })

export default function Licitaciones() {
  const [items, setItems] = useState<Licitacion[]>([])
  const [q, setQ] = useState('')
  const [estatus, setEstatus] = useState<Estatus | ''>('')
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)

  async function load() {
    setLoading(true)
    const { data } = await api.get<Licitacion[]>('/licitaciones', {
      params: { q: q || undefined, estatus: estatus || undefined },
    })
    setItems(data)
    setLoading(false)
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [estatus])

  async function changeEstatus(lic: Licitacion, value: Estatus) {
    const { data } = await api.patch<Licitacion>(`/licitaciones/${lic.id}`, { estatus: value })
    setItems((prev) => prev.map((x) => (x.id === data.id ? data : x)))
  }

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Licitaciones</h1>
          <p className="text-sm text-slate-500">{items.length} procedimientos</p>
        </div>
        <button className="btn-primary" onClick={() => setShowForm(true)}>
          + Nueva licitación
        </button>
      </div>

      <form
        className="mb-4 flex flex-wrap gap-2"
        onSubmit={(e) => {
          e.preventDefault()
          load()
        }}
      >
        <input
          className="input max-w-xs"
          placeholder="Buscar por título o número…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <select className="input max-w-[12rem]" value={estatus} onChange={(e) => setEstatus(e.target.value as Estatus | '')}>
          <option value="">Todos los estatus</option>
          {Object.entries(ESTATUS_LABEL).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
        <button className="btn-ghost border border-slate-300">Buscar</button>
      </form>

      <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-3">Procedimiento</th>
              <th className="px-4 py-3">Dependencia</th>
              <th className="px-4 py-3">Apertura</th>
              <th className="px-4 py-3 text-right">Monto estimado</th>
              <th className="px-4 py-3">Estatus</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {loading ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-slate-400">
                  Cargando…
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-slate-400">
                  Sin licitaciones todavía.
                </td>
              </tr>
            ) : (
              items.map((lic) => (
                <tr key={lic.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3">
                    <div className="font-medium">{lic.titulo}</div>
                    <div className="font-mono text-xs text-slate-500">
                      {lic.numero_procedimiento} · {TIPO_LABEL[lic.tipo]}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    {lic.dependencia}
                    {lic.entidad_federativa && <div className="text-xs text-slate-500">{lic.entidad_federativa}</div>}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3">
                    {lic.fecha_apertura ? dateFmt.format(new Date(lic.fecha_apertura)) : '—'}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-right tabular-nums">
                    {lic.monto_estimado ? money.format(Number(lic.monto_estimado)) : '—'}
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge value={lic.estatus} onChange={(v) => changeEstatus(lic, v)} />
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {showForm && (
        <NuevaLicitacion
          onClose={() => setShowForm(false)}
          onCreated={(lic) => {
            setItems((prev) => [lic, ...prev])
            setShowForm(false)
          }}
        />
      )}
    </div>
  )
}

function NuevaLicitacion({ onClose, onCreated }: { onClose: () => void; onCreated: (l: Licitacion) => void }) {
  const [form, setForm] = useState({
    numero_procedimiento: '',
    titulo: '',
    dependencia: '',
    entidad_federativa: '',
    tipo: 'licitacion_publica' as Tipo,
    fecha_apertura: '',
    monto_estimado: '',
    url_fuente: '',
  })
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const set = (k: keyof typeof form) => (e: { target: { value: string } }) =>
    setForm((f) => ({ ...f, [k]: e.target.value }))

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      const payload = Object.fromEntries(Object.entries(form).map(([k, v]) => [k, v === '' ? null : v]))
      const { data } = await api.post<Licitacion>('/licitaciones', payload)
      onCreated(data)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-10 flex items-center justify-center bg-black/40 px-4" onClick={onClose}>
      <form
        onSubmit={onSubmit}
        onClick={(e) => e.stopPropagation()}
        className="grid w-full max-w-2xl gap-4 rounded-xl bg-white p-6 shadow-xl sm:grid-cols-2"
      >
        <h2 className="text-lg font-semibold sm:col-span-2">Nueva licitación</h2>
        <div className="sm:col-span-2">
          <label className="label">Título</label>
          <input className="input" value={form.titulo} onChange={set('titulo')} required />
        </div>
        <div>
          <label className="label">Número de procedimiento</label>
          <input className="input font-mono" value={form.numero_procedimiento} onChange={set('numero_procedimiento')} required />
        </div>
        <div>
          <label className="label">Tipo</label>
          <select className="input" value={form.tipo} onChange={set('tipo')}>
            {Object.entries(TIPO_LABEL).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="label">Dependencia</label>
          <input className="input" placeholder="IMSS, ISSSTE, SSA…" value={form.dependencia} onChange={set('dependencia')} required />
        </div>
        <div>
          <label className="label">Entidad federativa</label>
          <input className="input" value={form.entidad_federativa} onChange={set('entidad_federativa')} />
        </div>
        <div>
          <label className="label">Apertura de proposiciones</label>
          <input className="input" type="datetime-local" value={form.fecha_apertura} onChange={set('fecha_apertura')} />
        </div>
        <div>
          <label className="label">Monto estimado (MXN)</label>
          <input className="input" type="number" min="0" step="0.01" value={form.monto_estimado} onChange={set('monto_estimado')} />
        </div>
        <div className="sm:col-span-2">
          <label className="label">URL fuente (ComprasMX / CompraNet)</label>
          <input className="input" type="url" value={form.url_fuente} onChange={set('url_fuente')} />
        </div>
        {error && <p className="text-sm text-red-600 sm:col-span-2">{error}</p>}
        <div className="flex justify-end gap-2 sm:col-span-2">
          <button type="button" className="btn-ghost" onClick={onClose}>
            Cancelar
          </button>
          <button className="btn-primary" disabled={saving}>
            {saving ? 'Guardando…' : 'Guardar'}
          </button>
        </div>
      </form>
    </div>
  )
}
