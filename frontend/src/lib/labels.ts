/** Etiquetas en español (México) para los códigos que devuelve la API. */
import type { DataKind } from '@/lib/types'

/** Si el código no está mapeado se muestra legible, sin inventar significado. */
export function humanize(code: string | null | undefined): string {
  if (!code) return ''
  const s = code.replace(/[_.]/g, ' ').trim()
  return s.charAt(0).toUpperCase() + s.slice(1)
}

function lookup(map: Record<string, string>, code: string | null | undefined): string {
  if (!code) return ''
  return map[code] ?? humanize(code)
}

export const DATA_KIND_LABEL: Record<DataKind, string> = {
  REAL: 'Real',
  HISTORICAL: 'Histórico',
  SYNTHETIC: 'Simulado',
}

export const DATA_KIND_CHIP_LABEL: Record<DataKind, string> = {
  REAL: 'REAL',
  HISTORICAL: 'HISTÓRICO',
  SYNTHETIC: 'SIMULADO',
}

export const DATA_KIND_HINT: Record<DataKind, string> = {
  REAL: 'Procedimiento consultado en una fuente oficial.',
  HISTORICAL: 'Referencia pública pasada; no es una oportunidad abierta.',
  SYNTHETIC: 'Escenario ficticio para la demostración; no existe en ninguna fuente.',
}

const PROCEDURE_TYPE: Record<string, string> = {
  licitacion_publica: 'Licitación pública',
  invitacion_3: 'Invitación a cuando menos tres personas',
  adjudicacion_directa: 'Adjudicación directa',
}
export const procedureTypeLabel = (c: string | null | undefined) => lookup(PROCEDURE_TYPE, c)

const CHARACTER: Record<string, string> = {
  nacional: 'Nacional',
  internacional_tlc: 'Internacional bajo tratados',
  internacional_abierta: 'Internacional abierta',
}
export const characterLabel = (c: string | null | undefined) => lookup(CHARACTER, c)

const SCOPE: Record<string, string> = {
  empresa: 'Empresa',
  producto: 'Producto',
  expediente: 'Expediente',
  partida: 'Partida',
  servicio: 'Servicio',
}
export const scopeLabel = (c: string | null | undefined) => lookup(SCOPE, c)

const REQ_TYPE: Record<string, string> = {
  tecnico: 'Técnico',
  documental: 'Documental',
  servicio: 'Servicio',
  capacidad: 'Capacidad',
  administrativo: 'Administrativo',
}
export const reqTypeLabel = (c: string | null | undefined) => lookup(REQ_TYPE, c)

const OPERATOR: Record<string, string> = { eq: '=', gte: '≥', lte: '≤', gt: '>', lt: '<', contains: 'contiene', in: 'uno de' }
export const operatorSymbol = (c: string | null | undefined) => (c ? OPERATOR[c] ?? c : '=')

const SOURCE_METHOD: Record<string, string> = {
  manual: 'Carga manual',
  scraper: 'Adaptador en servidor',
  api: 'API',
  fixture: 'Datos de demostración',
}
export const sourceMethodLabel = (c: string | null | undefined) => lookup(SOURCE_METHOD, c)

const DOC_TYPE: Record<string, string> = {
  certificado: 'Certificado',
  ficha_tecnica: 'Ficha técnica',
  carta: 'Carta',
  registro: 'Registro',
  constancia: 'Constancia',
  bases: 'Bases',
  tecnica_quirurgica: 'Técnica quirúrgica',
  folleto: 'Folleto',
  catalogo: 'Catálogo',
  otro: 'Otro',
}
export const docTypeLabel = (c: string | null | undefined) => lookup(DOC_TYPE, c)

const EVIDENCE_DECISION: Record<string, string> = {
  propuesta: 'Propuesta (sin revisar)',
  aceptada: 'Aceptada',
  rechazada: 'Rechazada',
}
export const evidenceDecisionLabel = (c: string | null | undefined) => lookup(EVIDENCE_DECISION, c)

const RESULT: Record<string, string> = {
  desconocido: 'Desconocido',
  unknown: 'Desconocido',
  adjudicado: 'Adjudicado',
  desierto: 'Desierto',
  cancelado: 'Cancelado',
  'fallo publicado': 'Fallo publicado',
  fallo_publicado: 'Fallo publicado',
}
export const resultLabel = (c: string | null | undefined) => lookup(RESULT, c)

const VERIFICATION: Record<string, string> = {
  por_verificar: 'Por verificar',
  verificada: 'Verificada',
  desactualizada: 'Desactualizada',
  fuente_inaccesible: 'Fuente inaccesible',
  simulada: 'Simulada',
}
export const verificationLabel = (c: string | null | undefined) => lookup(VERIFICATION, c)

const RESOURCE_TYPE: Record<string, string> = {
  opportunity: 'Oportunidad',
  requirement: 'Requisito',
  task: 'Actividad',
  document: 'Documento',
  product: 'Producto',
  user: 'Usuario',
  organization: 'Organización',
  source: 'Fuente',
  search_run: 'Búsqueda en vivo',
  bid_workspace: 'Expediente',
  generated_artifact: 'Borrador del expediente',
}
export const resourceTypeLabel = (c: string | null | undefined) => lookup(RESOURCE_TYPE, c)

const AUDIT_ACTION: Record<string, string> = {
  'auth.login': 'Inicio de sesión',
  'opportunity.create': 'Oportunidad creada',
  'opportunity.update': 'Oportunidad actualizada',
  'opportunity.import': 'Oportunidad importada manualmente',
  'search.start': 'Búsqueda en vivo iniciada',
  'search.finish': 'Búsqueda en vivo terminada',
  'document.create': 'Documento creado',
  'document.version_upload': 'Nueva versión de documento cargada',
  'document.download': 'Documento descargado',
  'document.file_repaired': 'Archivo de documento reparado',
  'document.link_product': 'Documento vinculado a un producto',
  'catalog.import': 'Catálogo importado',
  'demo.reset': 'Reinicio del demo',
  'requirement.evidence_linked': 'Evidencia vinculada (a revisión)',
  'requirement.review': 'Requisito revisado',
  'task.assign': 'Actividad asignada',
  'task.update': 'Actividad actualizada',
  'workspace.assess': 'Correspondencia evaluada',
  'workspace.decision': 'Decisión de participar',
  'workspace.approval': 'Aprobación del expediente',
  'workspace.approvals_invalidated': 'Aprobaciones sin efecto por un cambio',
  'workspace.ready': 'Listo para revisión final',
  'workspace.create': 'Expediente abierto',
  'artifact.generate': 'Borrador del expediente generado',
  'artifact.download': 'Borrador del expediente descargado',
  'audit.verify': 'Integridad de la bitácora verificada',
}
export const auditActionLabel = (c: string) => AUDIT_ACTION[c] ?? c

const FIELD: Record<string, string> = {
  owner_id: 'Responsable',
  notes: 'Notas',
  families: 'Familias',
  status: 'Estado',
  demo_base_date: 'Fecha base',
  variants: 'Variantes',
  historical: 'Referencias históricas',
  scenarios: 'Escenarios',
  documents: 'Documentos',
  requirements: 'Requisitos',
  tasks: 'Actividades',
  // Campos de los eventos de búsqueda, importación, documentos y catálogo
  terms: 'Términos',
  date_from: 'Fecha inicial',
  date_to: 'Fecha final',
  job_id: 'Tarea',
  counts: 'Conteos',
  errors: 'Fallos',
  external_id: 'Número de procedimiento',
  title: 'Título',
  buyer: 'Convocante',
  state: 'Entidad',
  data_kind: 'Tipo de dato',
  source_url: 'Enlace de la fuente',
  verification_status: 'Verificación',
  reported_status: 'Estado reportado',
  result: 'Resultado',
  questions_at: 'Junta de aclaraciones',
  submission_at: 'Presentación de propuestas',
  ruling_at: 'Fallo',
  method: 'Método',
  url: 'Enlace',
  outcome: 'Resultado de la importación',
  evidence_sha256: 'Huella de la evidencia',
  code: 'Código',
  scope: 'Alcance',
  doc_type: 'Tipo de documento',
  valid_until: 'Vigente hasta',
  product_id: 'Producto',
  opportunity_id: 'Oportunidad',
  third_party: 'De un tercero',
  external_url: 'Enlace externo',
  current_version: 'Versión vigente',
  review_status: 'Estado de revisión',
  version: 'Versión',
  filename: 'Archivo',
  content_type: 'Tipo de archivo',
  size_bytes: 'Tamaño (bytes)',
  sha256: 'Huella SHA-256',
  note: 'Nota',
  source: 'Fuente',
  checked_on: 'Consultado el',
  products: 'Productos',
  created: 'Creados',
  updated: 'Actualizados',
  warnings: 'Avisos',
  warning_messages: 'Detalle de avisos',
  // Campos de los eventos del expediente (requisitos, actividades y aprobaciones)
  status_reason: 'Motivo del estado',
  reviewer_id: 'Revisor',
  assignee_id: 'Responsable',
  due_date: 'Fecha límite',
  decision: 'Decisión',
  workspace: 'Expediente',
  evidence: 'Evidencia revisada',
  evidence_id: 'Evidencia',
  document_code: 'Documento',
  document_version: 'Versión del documento',
  page: 'Página',
  fragment: 'Fragmento',
  kind: 'Tipo de aprobación',
  requirement_code: 'Requisito',
  phase: 'Fase',
  approvals_stale: 'Aprobaciones desactualizadas',
  technical_approval_by_id: 'Aprobación técnica',
  commercial_approval_by_id: 'Aprobación comercial',
  decision_reason: 'Motivo de la decisión',
  decision_by_id: 'Decidió',
  decision_at: 'Fecha de la decisión',
  technical_approval_at: 'Fecha de la aprobación técnica',
  commercial_approval_at: 'Fecha de la aprobación comercial',
  approvals_cleared: 'Aprobaciones anuladas',
  requirement_id: 'Requisito',
  assignee: 'Responsable',
  workspace_id: 'Expediente',
  // Evaluación del motor y compuerta
  affinity: 'Afinidad',
  results: 'Resultados del motor',
  assessments: 'Requisitos evaluados',
  assessed: 'Ya evaluado',
  engine_version: 'Versión del motor',
  total: 'Afinidad total',
  blocking: 'Bloqueantes',
  origin: 'Origen',
  // Borradores del expediente
  templates: 'Plantillas',
  data_version: 'Versión de datos',
  template_version: 'Versión de plantillas',
  files: 'Archivos en el paquete',
  // Verificación de la bitácora
  ok: 'Cadena correcta',
  checked: 'Eventos verificados',
  first_broken_id: 'Primer evento alterado',
  last_hash: 'Último hash verificado',
}
export const fieldLabel = (c: string) => FIELD[c] ?? c

/** Resultado del motor determinista de correspondencia (`services/matching.py`). */
export const MATCH_RESULT_LABEL: Record<string, string> = {
  coincide: 'Coincide',
  incumple: 'Incumple',
  desconocido: 'Desconocido',
  no_comparable: 'No comparable',
}
export const matchResultText = (c: string | null | undefined) => lookup(MATCH_RESULT_LABEL, c)

/** Fases del expediente (`services/workspace.py`). */
export const PHASE_LABEL: Record<string, string> = {
  analisis: 'Análisis',
  preparacion: 'Preparación del expediente',
  listo_revision_final: 'Listo para revisión final',
  descartada: 'Descartada (no participar)',
}
export const phaseLabel = (c: string | null | undefined) => lookup(PHASE_LABEL, c)

/** Decisión de participar del responsable comercial. */
export const DECISION_LABEL: Record<string, string> = {
  pendiente: 'Sin decisión',
  participar: 'Participar',
  no_participar: 'No participar',
}
export const decisionLabel = (c: string | null | undefined) => lookup(DECISION_LABEL, c)

/** Tipo de aprobación del expediente. */
export const APPROVAL_KIND_LABEL: Record<string, string> = { tecnica: 'Técnica', comercial: 'Comercial' }
export const approvalKindLabel = (c: string | null | undefined) => lookup(APPROVAL_KIND_LABEL, c)

/** Atributos técnicos comparables: etiqueta y unidad canónica cuando el dato no la trae. */
const ATTRIBUTE: Record<string, { label: string; unit?: string }> = {
  material: { label: 'Material' },
  holes: { label: 'Orificios', unit: 'orificios' },
  size_demo: { label: 'Talla (demo)' },
  diameter_mm: { label: 'Diámetro', unit: 'mm' },
  length_mm: { label: 'Longitud', unit: 'mm' },
  width_mm: { label: 'Ancho', unit: 'mm' },
  stock_demo: { label: 'Existencia (simulada)' },
}
export const attributeLabel = (key: string) => ATTRIBUTE[key]?.label ?? humanize(key)
export const attributeUnit = (key: string) => ATTRIBUTE[key]?.unit

/** Entidades federativas de México (catálogo oficial de 32 entidades). */
export const MX_STATES = [
  'Aguascalientes',
  'Baja California',
  'Baja California Sur',
  'Campeche',
  'Chiapas',
  'Chihuahua',
  'Ciudad de México',
  'Coahuila',
  'Colima',
  'Durango',
  'Estado de México',
  'Guanajuato',
  'Guerrero',
  'Hidalgo',
  'Jalisco',
  'Michoacán',
  'Morelos',
  'Nayarit',
  'Nuevo León',
  'Oaxaca',
  'Puebla',
  'Querétaro',
  'Quintana Roo',
  'San Luis Potosí',
  'Sinaloa',
  'Sonora',
  'Tabasco',
  'Tamaulipas',
  'Tlaxcala',
  'Veracruz',
  'Yucatán',
  'Zacatecas',
]
