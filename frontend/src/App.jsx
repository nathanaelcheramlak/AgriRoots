import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import HomePage from "@/app/page";
import AuthOptionsPage from "@/app/auth-options/page";
import OnboardingLocationPage from "@/app/onboarding/location/page";
import OnboardingLanguagePage from "@/app/onboarding/language/page";
import OnboardingFarmingPage from "@/app/onboarding/farming/page";
import SettingsPage from "@/app/settings/page";
import { AuthProvider } from "@/contexts/AuthContext";
import { LanguageProvider } from "@/contexts/LanguageContext";

const WorkspacePage = lazy(() => import("@/app/workspace/page"));
const ReleasedPage = lazy(() => import("@/app/workspace/released"));
const MainPage = lazy(() => import("@/app/main-page/page"));

export default function App() {
  return (
    <AuthProvider>
      <LanguageProvider>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/auth-options" element={<AuthOptionsPage />} />
          <Route path="/main-page" element={<Suspense fallback={<p>Loading chat…</p>}><MainPage /></Suspense>} />
          <Route path="/onboarding/location" element={<OnboardingLocationPage />} />
          <Route path="/onboarding/language" element={<OnboardingLanguagePage />} />
          <Route path="/onboarding/farming" element={<OnboardingFarmingPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/workspace" element={<Suspense fallback={<p>Loading workspace…</p>}><WorkspacePage /></Suspense>} />
          <Route path="/advisories" element={<Suspense fallback={<p>Loading advisories…</p>}><ReleasedPage /></Suspense>} />
          <Route path="/alerts" element={<Navigate to="/advisories" replace />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </LanguageProvider>
    </AuthProvider>
  );
}
