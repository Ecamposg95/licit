import { Navigate, Route, Routes } from 'react-router-dom'
import Layout from '@/components/Layout'
import SessionGate from '@/components/SessionGate'
import Login from '@/pages/Login'
import Radar from '@/pages/Radar'
import OpportunityDetail from '@/pages/OpportunityDetail'
import Catalog from '@/pages/Catalog'
import CatalogProduct from '@/pages/catalog/ProductDetail'
import Documents from '@/pages/Documents'
import DocumentDetail from '@/pages/documents/DocumentDetail'
import Tasks from '@/pages/Tasks'
import Audit from '@/pages/Audit'
import Operations from '@/pages/Operations'
import Panel from '@/pages/Panel'
import Gobierno from '@/pages/Gobierno'
import TI from '@/pages/TI'

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
        <Route path="/catalogo/:productId" element={<CatalogProduct />} />
        <Route path="/documentos" element={<Documents />} />
        <Route path="/documentos/:id" element={<DocumentDetail />} />
        <Route path="/pendientes" element={<Tasks />} />
        <Route path="/bitacora" element={<Audit />} />
        <Route path="/operacion" element={<Operations />} />
        <Route path="/panel" element={<Panel />} />
        <Route path="/gobierno" element={<Gobierno />} />
        <Route path="/ti" element={<TI />} />
      </Route>
      <Route path="*" element={<Navigate to="/radar" replace />} />
    </Routes>
  )
}
