import { createContext, useContext, useMemo, useState } from "react";

const LanguageContext = createContext(null);

export const SUPPORTED_LANGUAGES = [
  { code: "en", tag: "US", name: "English" },
  { code: "am", tag: "ET", name: "አማርኛ" },
];

export const LANGUAGE_TO_BCP47 = {
  en: "en-US",
  am: "am-ET",
};

export function getVoiceLanguageCode(language) {
  return LANGUAGE_TO_BCP47[language] || LANGUAGE_TO_BCP47.en;
}

export function LanguageProvider({ children }) {
  const [language, setLanguageState] = useState(() => {
    const saved = localStorage.getItem("farmly_language");
    return saved === "en" || saved === "am" ? saved : "en";
  });

  const value = useMemo(
    () => ({
      language,
      setLanguage: (next) => {
        localStorage.setItem("farmly_language", next);
        setLanguageState(next);
      },
    }),
    [language]
  );

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useLanguage() {
  const ctx = useContext(LanguageContext);
  if (!ctx) {
    throw new Error("useLanguage must be used inside LanguageProvider");
  }
  return ctx;
}
