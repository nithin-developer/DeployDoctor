import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "@/components/ui/sonner";
import { NavigationProgress } from "@/components/navigation-progress";
import { useAuthStore } from "@/stores/authStore";
import { AuthenticatedLayout } from "@/components/layout/authenticated-layout";
import { handleServerError } from "@/utils/handle-server-error";
import { AxiosError } from "axios";

// Import debug utilities in development
if (import.meta.env.DEV) {
  import("@/utils/debug-auth");
}

// Pages
import Dashboard from "@/pages/dashboard";
import SignIn from "@/pages/auth/sign-in";
import SignUp from "@/pages/auth/sign-up";
import TwoFAVerify from "@/pages/auth/two-fa-verify";
import ForgotPassword from "@/pages/auth/forgot-password";
import Otp from "@/pages/auth/otp";
import NotFoundError from "@/pages/errors/not-found-error";
import GeneralError from "@/pages/errors/general-error";
import UnauthorizedError from "@/pages/errors/unauthorized-error";
import ForbiddenError from "@/pages/errors/forbidden";
import MaintenanceError from "@/pages/errors/maintenance-error";

// Protected Route Component
import { ProtectedRoute } from "@/components/auth/protected-route";

// Batches Feature Pages
import Settings from "./pages/settings";
import SettingsAccount from "./pages/settings/account";
import SettingsAppearance from "./pages/settings/appearance";
import SettingsSecurity from "./pages/settings/security";
import SettingsTwoFA from "./pages/settings/2fa-auth";

// Analysis Pages
import AnalysisPage from "./pages/analysis";
import AnalysisResultPage from "./pages/analysis/result";

// Create Query Client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (failureCount, error) => {
        if (import.meta.env.DEV) console.log({ failureCount, error });

        if (failureCount >= 0 && import.meta.env.DEV) return false;
        if (failureCount > 3 && import.meta.env.PROD) return false;

        return !(
          error instanceof AxiosError &&
          [401, 403].includes(error.response?.status ?? 0)
        );
      },
      refetchOnWindowFocus: import.meta.env.PROD,
      staleTime: 10 * 1000, // 10s
    },
    mutations: {
      onError: (error) => {
        handleServerError(error);

        if (error instanceof AxiosError) {
          if (error.response?.status === 304) {
            return; // Do nothing for 304
          }
        }
      },
    },
  },
});

// Authentication Guard Component
function AuthGuard({ children }: { children: React.ReactNode }) {
  const auth = useAuthStore();

  console.log("AuthGuard check:", {
    isAuthenticated: auth.auth.isAuthenticated(),
    hasUser: !!auth.auth.user,
    hasToken: !!auth.auth.accessToken,
    user: auth.auth.user
      ? {
          email: auth.auth.user.email,
        }
      : null,
  });

  if (import.meta.env.VITE_ENVIRONMENT !== "development")
    console.log = () => {};

  if (!auth.auth.isAuthenticated()) {
    console.log("User not authenticated, redirecting to sign-in");
    return <Navigate to="/sign-in" replace />;
  }

  console.log("User authenticated, showing protected content");
  return <>{children}</>;
}

// Authentication Redirect Component - redirects authenticated users away from auth pages
function AuthRedirect({ children }: { children: React.ReactNode }) {
  const auth = useAuthStore();
  if (auth.auth.isAuthenticated()) {
    return <Navigate to="/" replace />;
  }
  return <>{children}</>;
}

// Main App Component
function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <NavigationProgress />
        <Routes>
          {/* Public Routes */}
          <Route
            path="/sign-in"
            element={
              <AuthRedirect>
                <SignIn />
              </AuthRedirect>
            }
          />
          <Route
            path="/sign-up"
            element={
              <AuthRedirect>
                <SignUp />
              </AuthRedirect>
            }
          />
          <Route path="/two-fa-verify" element={<TwoFAVerify />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/otp" element={<Otp />} />

          {/* Error Routes */}
          <Route path="/401" element={<UnauthorizedError />} />
          <Route path="/403" element={<ForbiddenError />} />
          <Route path="/404" element={<NotFoundError />} />
          <Route path="/500" element={<GeneralError />} />
          <Route path="/503" element={<MaintenanceError />} />

          {/* Protected Routes */}
          <Route
            path="/"
            element={
              <AuthGuard>
                <AuthenticatedLayout />
              </AuthGuard>
            }
          >
            {/* Dashboard */}
            <Route index element={<Dashboard />} />

            {/* Analysis Routes */}
            <Route path="analysis" element={<AnalysisPage />} />
            <Route path="analysis/:analysisId" element={<AnalysisResultPage />} />

            {/* Settings Routes - Available for all authenticated users */}
            <Route path="settings" element={<Settings />}>
              <Route index element={<Navigate to="account" replace />} />
              <Route path="account" element={<SettingsAccount />} />
              <Route path="appearance" element={<SettingsAppearance />} />
              <Route path="security" element={<SettingsSecurity />} />
              <Route
                path="two-factor-authentication"
                element={<SettingsTwoFA />}
              />
            </Route>
          </Route>

          {/* Catch all route */}
          <Route path="*" element={<NotFoundError />} />
        </Routes>

        {/* Sonner Toaster for notifications */}
        <Toaster duration={5000} />
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
