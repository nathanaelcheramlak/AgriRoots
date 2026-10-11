import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Globe, Leaf } from "lucide-react";
import { Button } from "@/components/ui/button";
import { SUPPORTED_LANGUAGES, useLanguage } from "@/contexts/LanguageContext";

const COPY = {
  en: {
    brand: "Farmly",
    signIn: "Sign In",
    heroTitle: "Empowering Farmers with AI-Powered Agricultural Insights",
    heroSubtitle:
      "Get crop recommendations, weather guidance, fertilizer advice, and disease diagnosis in one simple place.",
    getStarted: "Get Started",
  },
  am: {
    brand: "Farmly",
    signIn: "ግባ",
    heroTitle: "ገበሬዎችን በAI የታገዘ የግብርና ምክር ማብቃት",
    heroSubtitle:
      "የሰብል ምክር፣ የአየር ሁኔታ መመሪያ፣ የማዳበሪያ ምክር እና የበሽታ ምርመራ በአንድ ቀላል ቦታ።",
    getStarted: "ጀምር",
  },
};

export default function HomePage() {
  const { language, setLanguage } = useLanguage();
  const copy = COPY[language] || COPY.en;
  const [showLanguageDropdown, setShowLanguageDropdown] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const languageMenuRef = useRef(null);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 30);
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    function handleOutsideClick(event) {
      if (languageMenuRef.current && !languageMenuRef.current.contains(event.target)) {
        setShowLanguageDropdown(false);
      }
    }

    document.addEventListener("mousedown", handleOutsideClick);
    return () => document.removeEventListener("mousedown", handleOutsideClick);
  }, []);

  return (
    <div className="relative min-h-[100dvh] w-full overflow-x-hidden bg-background">
      <div
        className={[
          "fixed z-50 flex w-full items-center justify-between px-4 py-3 transition-all duration-300 sm:px-6",
          scrolled
            ? "left-1/2 top-4 w-[95vw] max-w-3xl -translate-x-1/2 rounded-3xl border border-border bg-white/95 shadow-lg"
            : "left-0 top-0 border-none bg-transparent",
        ].join(" ")}
      >
        <span
          className={`flex items-center gap-2 text-lg font-bold transition-colors duration-300 ${
            scrolled ? "text-black" : "text-white"
          }`}
        >
          <Leaf className={`h-6 w-6 ${scrolled ? "text-green-600" : "text-white"}`} />
          {copy.brand}
        </span>

        <div className="flex items-center gap-2">
          <div className="relative" ref={languageMenuRef}>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowLanguageDropdown((v) => !v)}
              className={`px-3 py-1 text-xs font-medium transition-all duration-300 ${
                scrolled ? "text-gray-700 hover:bg-gray-100" : "text-white hover:bg-white/20"
              }`}
            >
              <Globe className="mr-1 h-4 w-4" />
              {SUPPORTED_LANGUAGES.find((l) => l.code === language)?.tag || "US"}
            </Button>

            <div
              className={`absolute right-0 z-50 mt-2 w-44 rounded-md border border-gray-200 bg-white shadow-lg transition-all duration-200 ease-out ${
                showLanguageDropdown
                  ? "visible translate-y-0 scale-100 opacity-100"
                  : "invisible -translate-y-2 scale-95 opacity-0"
              }`}
            >
              <div className="py-1">
                {SUPPORTED_LANGUAGES.map((lang) => (
                  <button
                    key={lang.code}
                    onClick={() => {
                      setLanguage(lang.code);
                      setShowLanguageDropdown(false);
                    }}
                    className={`flex w-full items-center gap-2 px-4 py-2 text-left text-sm hover:bg-gray-100 ${
                      language === lang.code ? "bg-green-50 text-green-700" : "text-gray-700"
                    }`}
                  >
                    <span className="font-medium">{lang.tag}</span>
                    <span>{lang.name}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>

          <Button
            className={`px-3 py-1 text-xs font-medium transition-all duration-300 ${
              scrolled ? "bg-primary text-white hover:bg-green-900" : "bg-white text-gray-900 hover:bg-white/80"
            }`}
          >
            <Link to="/auth-options">{copy.signIn}</Link>
          </Button>
        </div>
      </div>

      <section
        className="relative min-h-[100dvh] w-full bg-cover bg-center bg-no-repeat"
        style={{ backgroundImage: "url('/img-4.jpg')" }}
      >
        <div className="pointer-events-none absolute inset-0 bg-black/40" />
        <div className="relative z-10 mx-auto flex min-h-[100dvh] max-w-5xl flex-col items-center justify-center px-4 py-24 text-center sm:px-6">
          <h1 className="max-w-4xl text-3xl font-bold tracking-tight text-white sm:text-4xl md:text-5xl">
            {copy.heroTitle}
          </h1>
          <p className="mt-4 max-w-2xl text-sm text-green-100 sm:text-base md:text-lg">{copy.heroSubtitle}</p>
          <div className="mt-7">
            <Button className="bg-green-600 px-6 py-2 text-white hover:bg-green-700">
              <Link to="/auth-options">{copy.getStarted}</Link>
            </Button>
          </div>
        </div>
      </section>
    </div>
  );
}
