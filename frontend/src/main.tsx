import { StrictMode } from "react";
import ReactDOM from "react-dom/client";
import { useAuthStore } from "@/stores/authStore";
import { fetchMe } from "@/api/auth";
import { FontProvider } from "./context/font-context";
import { ThemeProvider } from "./context/theme-context";
import "./index.css";
import App from "./App";

// Attach listener once to run after (re)hydration
const auth = useAuthStore.getState().auth;
async function bootstrapAuth() {
  if (!auth.accessToken) return;
  // ensure token valid (refresh if needed via ensureFreshAccess) else manual refresh
  try {
    await fetchMe().then((user) => {
      if (user)
        auth.setSession({
          user,
          accessToken: auth.accessToken!,
          refreshToken: "cookie",
        });
    });
  } catch (e: any) {
    // If still 401 after built-in fetchMe refresh attempt, reset
    auth.reset();
  }
}
bootstrapAuth();
// Re-run after rehydrate if token appears later
useAuthStore.persist?.onFinishHydration?.(() => {
  bootstrapAuth();
});

// Render the app
const rootElement = document.getElementById("root")!;
if (!rootElement.innerHTML) {
  const root = ReactDOM.createRoot(rootElement);
  root.render(
    <StrictMode>
      <ThemeProvider defaultTheme="light" storageKey="vite-ui-theme">
        <FontProvider>
          <App />
        </FontProvider>
      </ThemeProvider>
    </StrictMode>
  );
}
