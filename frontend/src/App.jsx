import { Navigate, Route, Routes } from "react-router-dom";
import HomePage from "@/app/page";
import AuthOptionsPage from "@/app/auth-options/page";
import MainPage from "@/app/main-page/page";
import OnboardingLocationPage from "@/app/onboarding/location/page";
import OnboardingLanguagePage from "@/app/onboarding/language/page";
import OnboardingFarmingPage from "@/app/onboarding/farming/page";
import SettingsPage from "@/app/settings/page";
import AlertsPage from "@/app/alerts/page";
import { AuthProvider } from "@/contexts/AuthContext";
import { LanguageProvider } from "@/contexts/LanguageContext";

export default function App() {
  return (
    <AuthProvider>
      <LanguageProvider>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/auth-options" element={<AuthOptionsPage />} />
          <Route path="/main-page" element={<MainPage />} />
          <Route path="/onboarding/location" element={<OnboardingLocationPage />} />
          <Route path="/onboarding/language" element={<OnboardingLanguagePage />} />
          <Route path="/onboarding/farming" element={<OnboardingFarmingPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/alerts" element={<AlertsPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </LanguageProvider>
    </AuthProvider>
  );
}
