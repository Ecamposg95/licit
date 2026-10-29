import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { User } from '@/lib/api'

interface AuthState {
  token: string | null
  user: User | null
  setSession: (token: string, user: User) => void
  logout: () => void
}

export const useAuth = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      setSession: (token, user) => set({ token, user }),
      logout: () => set({ token: null, user: null }),
    }),
    { name: 'licit-auth' },
  ),
)
