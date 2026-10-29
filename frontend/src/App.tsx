import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from '@/store/auth'
import Layout from '@/components/Layout'
import Login from '@/pages/Login'
import Licitaciones from '@/pages/Licitaciones'

function RequireAuth({ children }: { children: JSX.Element }) {
  const token = useAuth((s) => s.token)
  return token ? children : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route path="/" element={<Navigate to="/licitaciones" replace />} />
        <Route path="/licitaciones" element={<Licitaciones />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
