import axios from "axios";
import { useAuthStore } from "@/stores/authStore";

const baseURL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export const apiClient = axios.create({
  baseURL,
  withCredentials: true,
  timeout: 15000,
  headers: { "Content-Type": "application/json" },
});

let accessToken: string | null = null;

export function setAuthTokens(access: string | null) {
  accessToken = access;
}

export function clearAuthTokens() {
  accessToken = null;
}

// Shared single-flight refresh promise (response interceptor only)
let activeRefresh: Promise<string | null> | null = null;

apiClient.interceptors.request.use((config) => {
  // Only attach existing token; do NOT block request with proactive refresh
  if (accessToken) {
    config.headers = config.headers || {};
    (config.headers as any)["Authorization"] = `Bearer ${accessToken}`;
  }
  return config;
});

// Single-flight refresh handling to avoid storm & loops
// activeRefresh declared above for both interceptors

apiClient.interceptors.response.use(
  (r) => r,
  async (error) => {
    const original: any = error.config;
    // If no config, or we've already retried, or this request opts out, just reject
    if (!original || original._retry || original._skipAuthRefresh)
      return Promise.reject(error);

    // Don't attempt refresh for auth endpoints themselves to avoid loops
    const url: string = original.url || "";
    if (
      url.includes("/api/auth/refresh") ||
      url.includes("/api/auth/login") ||
      url.includes("/api/auth/verify-2fa")
    ) {
      return Promise.reject(error);
    }

    if (error.response?.status === 401) {
      original._retry = true;
      try {
        if (!activeRefresh) {
          activeRefresh = refreshAccessToken().finally(() => {
            activeRefresh = null;
          });
        }
        const newAccess = await activeRefresh;
        if (newAccess) {
          original.headers = original.headers || {};
          original.headers["Authorization"] = `Bearer ${newAccess}`;
          return apiClient(original);
        }
      } catch {
        // Hard logout on refresh failure after a 401
        const store = useAuthStore.getState().auth;
        store.reset();
        try {
          window.dispatchEvent(new CustomEvent('auth:logout'));
        } catch {}
      }
    }
    return Promise.reject(error);
  }
);

export async function refreshAccessToken(): Promise<string | null> {
  try {
    const res = await apiClient.post("/api/auth/refresh", undefined, {
      _skipAuthRefresh: true,
    } as any);
    const { access_token } = res.data || {};
    if (access_token) {
      const auth = useAuthStore.getState().auth;
      if (auth.user) {
        auth.setSession({
          user: auth.user,
          accessToken: access_token,
          refreshToken: "cookie",
        });
      } else {
        setAuthTokens(access_token);
      }
      return access_token;
    }
    return null;
  } catch {
    return null;
  }
}

export async function logoutRequest() {
  try {
    await apiClient.post("/api/auth/logout");
  } catch {}
}
