import { create } from "zustand";
import { persist } from "zustand/middleware";
import { setAuthTokens, clearAuthTokens, refreshAccessToken } from "@/api/http";

export interface AuthUser {
  id: string;
  email: string;
  full_name?: string;
  is_2fa_enabled?: boolean;
  created_at?: string;
  updated_at?: string;
}

interface AuthSlice {
  user: AuthUser | null;
  accessToken: string | null;
  refreshToken: string | null;
  expiresAt: number | null;
  isAuthenticated: () => boolean;
  setSession: (p: {
    user: AuthUser;
    accessToken: string;
    refreshToken: string;
    expiresInSec?: number;
  }) => void;
  reset: () => void;
  ensureFreshAccess: () => Promise<string | null>;
}

interface AuthStore { auth: AuthSlice }

const ACCESS_SAFETY_WINDOW_MS = 30_000; // refresh 30s before expiry

function decodeJwt(token: string): { exp?: number } {
  try {
    const payload = token.split(".")[1];
    const json = atob(payload.replace(/-/g, "+").replace(/_/g, "/"));
    return JSON.parse(json);
  } catch {
    return {};
  }
}

export const useAuthStore = create<AuthStore>()(
  persist(
    (set, get) => ({
      auth: {
        user: null,
        accessToken: null,
        refreshToken: null,
        expiresAt: null,
        isAuthenticated: () => !!get().auth.accessToken && !!get().auth.user,
        setSession: ({ user, accessToken, refreshToken, expiresInSec }) => {
          const expiresAt =
            Date.now() + (expiresInSec ? expiresInSec * 1000 : 15 * 60 * 1000);
          set({
            auth: { ...get().auth, user, accessToken, refreshToken, expiresAt },
          });
          setAuthTokens(accessToken);
        },
        reset: () => {
          clearAuthTokens();
          set({
            auth: {
              user: null,
              accessToken: null,
              refreshToken: null,
              expiresAt: null,
              isAuthenticated: get().auth.isAuthenticated,
              setSession: get().auth.setSession,
              reset: get().auth.reset,
              ensureFreshAccess: get().auth.ensureFreshAccess,
            },
          });
        },
        ensureFreshAccess: async () => {
          const st = get().auth;
          if (!st.accessToken) return null;
          const { exp } = decodeJwt(st.accessToken);
          const nowMs = Date.now();
          // Fallback to stored expiresAt if no exp claim
          const expMs = exp ? exp * 1000 : st.expiresAt || 0;
          if (expMs - nowMs > ACCESS_SAFETY_WINDOW_MS) return st.accessToken;
          try {
            const newTok = await refreshAccessToken();
            if (newTok) return newTok;
          } catch {
            st.reset();
          }
          return null;
        },
      },
    }),
    {
      name: "auth-store",
      // Only persist serializable data, not the methods
      partialize: (state: AuthStore) => ({
        auth: {
          user: state.auth.user,
          accessToken: state.auth.accessToken,
          refreshToken: state.auth.refreshToken,
          expiresAt: state.auth.expiresAt,
        },
      }),
      merge: (persisted: any, current: any) => {
        // Reconstruct slice keeping existing methods
        if (!persisted) return current;
        const data = persisted.auth || {};
        return {
          auth: {
            ...current.auth,
            ...data,
          },
        } as AuthStore;
      },
      onRehydrateStorage: () => (state) => {
        if (state?.auth.accessToken) setAuthTokens(state.auth.accessToken);
      },
    }
  )
);

export const useAuth = () => useAuthStore((state) => state.auth);
