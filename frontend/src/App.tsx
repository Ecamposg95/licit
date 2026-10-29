import { Navigate, Route, Routes } from 'react-router-dom'
import Layout from '@/components/Layout'
import SessionGate from '@/components/SessionGate'
import Login from '@/pages/Login'
import Radar from '@/pages/Radar'
import OpportunityDetail from '@/pages/OpportunityDetail'
import Catalog from '@/pages/Catalog'
import Documents from '@/pages/Documents'
import Tasks from '@/pages/Tasks'
import Audit from '@/pages/Audit'
import Operations from '@/pages/Operations'

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        element={
          <SessionGate>
            <Layout />
          </SessionGate>
        }
      >
        <Route index element={<Navigate to="/radar" replace />} />
        <Route path="/radar" element={<Radar />} />
        <Route path="/oportunidades/:id" element={<OpportunityDetail />} />
        <Route path="/catalogo" element={<Catalog />} />
        <Route path="/documentos" element={<Documents />} />
        <Route path="/pendientes" element={<Tasks />} />
        <Route path="/bitacora" element={<Audit />} />
        <Route path="/operacion" element={<Operations />} />
      </Route>
      <Route path="*" element={<Navigate to="/radar" replace />} />
    </Routes>
  )
}
