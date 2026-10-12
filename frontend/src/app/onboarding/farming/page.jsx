import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, ArrowRight, ChevronDown, Plus, User, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/contexts/AuthContext";
import { useLanguage } from "@/contexts/LanguageContext";
import { api } from "@/lib/api";

const USER_TYPE_OPTIONS = [
  { value: "aspiring", label: { en: "Aspiring farmer", am: "ገበሬ መሆን የሚፈልግ" } },
  { value: "beginner", label: { en: "Beginner farmer", am: "ጀማሪ ገበሬ" } },
  { value: "experienced", label: { en: "Experienced farmer", am: "ልምድ ያለው ገበሬ" } },
  { value: "explorer", label: { en: "Explorer", am: "ለመማር የሚፈልግ" } },
];

const MAIN_GOAL_OPTIONS = [
  { value: "increase_yield", label: { en: "Increase crop yield", am: "የሰብል ምርት መጨመር" } },
  { value: "reduce_costs", label: { en: "Reduce farming costs", am: "የእርሻ ወጪ መቀነስ" } },
  { value: "sustainable_farming", label: { en: "Sustainable farming", am: "ዘላቂ ግብርና" } },
  { value: "organic_farming", label: { en: "Organic farming", am: "ኦርጋኒክ ግብርና" } },
  { value: "market_access", label: { en: "Better market access", am: "የተሻለ የገበያ መዳረሻ" } },
];

const COPY = {
  en: {
    fallbackError: "Failed to complete onboarding. Please try again.",
    title: "Tell Us About Your Farming",
    subtitle: "This helps us personalize recommendations for you.",
    preferredLanguage: "Preferred Language",
    english: "English",
    amharic: "Amharic",
    farmingExperience: "Farming Experience",
    farmingExperiencePlaceholder: "Farming Experience",
    yearsExperience: "Years of Experience",
    yearsPlaceholder: "Please select years of experience",
    year: "year",
    years: "years",
    mainGoal: "Main Goal",
    mainGoalPlaceholder: "Main Goal",
    cropsGrown: "Crops Grown",
    cropPlaceholder: "Add crop (example: maize)",
    removeCrop: (crop) => `Remove ${crop}`,
    addAtLeastOneCrop: "Add at least one crop.",
    back: "Back",
    saving: "Saving...",
    complete: "Complete Onboarding",
    missingPrefix: "Please complete",
    missing: {
      accountName: "account name",
      location: "location",
      preferredLanguage: "preferred language",
      farmingExperience: "farming experience",
      yearsExperience: "years of experience",
      mainGoal: "main goal",
      crop: "at least one crop",
    },
  },
  am: {
    fallbackError: "ኦንቦርዲንግ ማጠናቀቅ አልተቻለም። እባክዎ እንደገና ይሞክሩ።",
    title: "ስለ እርሻዎ ይንገሩን",
    subtitle: "ይህ ለእርስዎ የተስማማ ምክር እንድንሰጥ ይረዳናል።",
    preferredLanguage: "የሚመርጡት ቋንቋ",
    english: "እንግሊዝኛ",
    amharic: "አማርኛ",
    farmingExperience: "የግብርና ልምድ",
    farmingExperiencePlaceholder: "የግብርና ልምድ",
    yearsExperience: "የልምድ ዓመታት",
    yearsPlaceholder: "የልምድ ዓመታትን ይምረጡ",
    year: "ዓመት",
    years: "ዓመታት",
    mainGoal: "ዋና ግብ",
    mainGoalPlaceholder: "ዋና ግብ",
    cropsGrown: "የሚያበቅሏቸው ሰብሎች",
    cropPlaceholder: "ሰብል ያክሉ (ምሳሌ፦ በቆሎ)",
    removeCrop: (crop) => `${crop} አስወግድ`,
    addAtLeastOneCrop: "ቢያንስ አንድ ሰብል ያክሉ።",
    back: "ተመለስ",
    saving: "በማስቀመጥ ላይ...",
    complete: "ኦንቦርዲንግ ጨርስ",
    missingPrefix: "እባክዎ ይሙሉ",
    missing: {
      accountName: "የመለያ ስም",
      location: "ቦታ",
      preferredLanguage: "የሚመርጡት ቋንቋ",
      farmingExperience: "የግብርና ልምድ",
      yearsExperience: "የልምድ ዓመታት",
      mainGoal: "ዋና ግብ",
      crop: "ቢያንስ አንድ ሰብል",
    },
  },
};

function SelectField({ id, value, onChange, children }) {
  return (
    <div className="relative w-full">
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-11 w-full appearance-none rounded-xl border border-green-300 bg-white px-4 pr-10 text-sm text-green-900 outline-none transition-all duration-200 ease-out focus:border-green-500 focus:ring-2 focus:ring-green-200"
      >
        {children}
      </select>
      <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-green-500 transition-transform duration-200" />
    </div>
  );
}

function errorMessageFrom(error, fallback) {
  const detail = error?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const msgs = detail.map((d) => d?.msg).filter(Boolean);
    if (msgs.length) return msgs.join(", ");
  }
  return error?.message || fallback;
}

export default function OnboardingFarmingPage() {
  const navigate = useNavigate();
  const { accessToken, isHydrated } = useAuth();
  const { language, setLanguage } = useLanguage();
  const copy = COPY[language] || COPY.en;

  const [isLoading, setIsLoading] = useState(false);
  const [isPrefilling, setIsPrefilling] = useState(true);
  const [error, setError] = useState("");

  const [locationString, setLocationString] = useState(
    () => sessionStorage.getItem("farmly_onboarding_location_string") || ""
  );
  const [cropInput, setCropInput] = useState("");
  const [formData, setFormData] = useState({
    full_name: "",
    phone_number: "",
    preferred_language: sessionStorage.getItem("farmly_onboarding_language") || "en",
    user_type: "",
    years_experience: "0",
    main_goal: "",
    crops_grown: [],
  });

  useEffect(() => {
    if (!isHydrated) return;
    if (!accessToken) {
      navigate("/auth-options", { replace: true });
    }
  }, [accessToken, isHydrated, navigate]);

  useEffect(() => {
    if (!isHydrated || !accessToken) return;

    api
      .get("/api/users/me/profile")
      .then(({ data }) => {
        if (!locationString.trim() && data?.location) {
          setLocationString(data.location);
        }
        setFormData((prev) => ({
          ...prev,
          full_name: data?.full_name || prev.full_name,
          phone_number: data?.phone_number || prev.phone_number,
          preferred_language: data?.preferred_language || prev.preferred_language || language || "en",
        }));
      })
      .catch(() => {})
      .finally(() => setIsPrefilling(false));
  }, [accessToken, isHydrated, language, locationString, navigate]);

  useEffect(() => {
    if (!isHydrated || isPrefilling) return;
    if (!locationString.trim()) {
      navigate("/onboarding/location", { replace: true });
    }
  }, [isHydrated, isPrefilling, locationString, navigate]);

  function addCrop() {
    const normalized = cropInput.trim().toLowerCase();
    if (!normalized) return;
    setFormData((prev) => {
      if (prev.crops_grown.includes(normalized)) return prev;
      return {
        ...prev,
        crops_grown: [...prev.crops_grown, normalized],
      };
    });
    setCropInput("");
  }

  function removeCrop(crop) {
    setFormData((prev) => ({
      ...prev,
      crops_grown: prev.crops_grown.filter((item) => item !== crop),
    }));
  }

  const formIsValid = useMemo(
    () =>
      formData.full_name.trim().length >= 2 &&
      locationString.trim().length >= 2 &&
      formData.preferred_language.trim().length >= 2 &&
      formData.user_type &&
      formData.main_goal &&
      formData.crops_grown.length >= 1 &&
      Number(formData.years_experience) >= 0 &&
      Number(formData.years_experience) <= 80,
    [formData, locationString]
  );

  async function handleSubmit() {
    const missingFields = [];
    if (!formData.full_name.trim()) missingFields.push(copy.missing.accountName);
    if (!locationString.trim()) missingFields.push(copy.missing.location);
    if (!formData.preferred_language.trim()) missingFields.push(copy.missing.preferredLanguage);
    if (!formData.user_type) missingFields.push(copy.missing.farmingExperience);
    if (!formData.years_experience.trim()) missingFields.push(copy.missing.yearsExperience);
    if (!formData.main_goal) missingFields.push(copy.missing.mainGoal);
    if (formData.crops_grown.length < 1) missingFields.push(copy.missing.crop);

    if (missingFields.length > 0 || !formIsValid) {
      setError(`${copy.missingPrefix}: ${missingFields.join(", ")}.`);
      return;
    }

    setError("");
    setIsLoading(true);
    try {
      await api.post("/api/onboarding/complete", {
        full_name: formData.full_name.trim(),
        phone_number: formData.phone_number.trim() || null,
        location: locationString.trim(),
        preferred_language: formData.preferred_language,
        user_type: formData.user_type,
        years_experience: Number(formData.years_experience),
        main_goal: formData.main_goal,
        crops_grown: formData.crops_grown,
      });

      sessionStorage.removeItem("farmly_onboarding_location");
      sessionStorage.removeItem("farmly_onboarding_location_string");
      sessionStorage.removeItem("farmly_onboarding_language");
      navigate("/main-page");
    } catch (submitError) {
      setError(errorMessageFrom(submitError, copy.fallbackError));
    } finally {
      setIsLoading(false);
    }
  }

  if (!isHydrated || isPrefilling) return null;

  return (
    <main className="min-h-screen bg-gradient-to-br from-green-50 to-green-100 px-4 py-6 sm:px-6 sm:py-10">
      <div className="mx-auto w-full max-w-md">
        <div className="mb-6 text-center sm:mb-8">
          <div className="mx-auto mb-3 flex h-16 w-16 items-center justify-center rounded-full bg-green-500 sm:h-20 sm:w-20">
            <User className="h-8 w-8 text-white sm:h-10 sm:w-10" />
          </div>
          <h1 className="text-2xl font-bold text-green-800 sm:text-3xl">{copy.title}</h1>
          <p className="mt-2 text-sm text-green-700 sm:text-base">
            {copy.subtitle}
          </p>
        </div>

        <Card className="rounded-2xl border-2 border-green-100 shadow-lg">
          <CardContent className="space-y-4 p-5 sm:p-6">
            <div className="space-y-2">
              <Label htmlFor="preferred_language">{copy.preferredLanguage}</Label>
              <SelectField
                id="preferred_language"
                value={formData.preferred_language}
                onChange={(value) => {
                  setFormData((prev) => ({ ...prev, preferred_language: value }));
                  setLanguage(value);
                  sessionStorage.setItem("farmly_onboarding_language", value);
                }}
              >
                <option value="en">{copy.english}</option>
                <option value="am">{copy.amharic}</option>
              </SelectField>
            </div>

            <div className="space-y-2">
              <Label htmlFor="user_type">{copy.farmingExperience}</Label>
              <SelectField
                id="user_type"
                value={formData.user_type}
                onChange={(value) => setFormData((prev) => ({ ...prev, user_type: value }))}
              >
                <option value="">{copy.farmingExperiencePlaceholder}</option>
                {USER_TYPE_OPTIONS.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label[language] || item.label.en}
                  </option>
                ))}
              </SelectField>
            </div>

            <div className="space-y-2">
              <Label htmlFor="years_experience">{copy.yearsExperience}</Label>
              <SelectField
                id="years_experience"
                value={formData.years_experience}
                onChange={(value) => setFormData((prev) => ({ ...prev, years_experience: value }))}
              >
                <option value="">{copy.yearsPlaceholder}</option>
                {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 15, 20, 25, 30].map((years) => (
                  <option key={years} value={String(years)}>
                    {years} {years === 1 ? copy.year : copy.years}
                  </option>
                ))}
              </SelectField>
            </div>

            <div className="space-y-2">
              <Label htmlFor="main_goal">{copy.mainGoal}</Label>
              <SelectField
                id="main_goal"
                value={formData.main_goal}
                onChange={(value) => setFormData((prev) => ({ ...prev, main_goal: value }))}
              >
                <option value="">{copy.mainGoalPlaceholder}</option>
                {MAIN_GOAL_OPTIONS.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label[language] || item.label.en}
                  </option>
                ))}
              </SelectField>
            </div>

            <div className="space-y-3">
              <Label>{copy.cropsGrown}</Label>
              <div className="flex gap-2">
                <Input
                  value={cropInput}
                  onChange={(e) => setCropInput(e.target.value)}
                  placeholder={copy.cropPlaceholder}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      addCrop();
                    }
                  }}
                />
                <Button type="button" onClick={addCrop} className="bg-green-500 text-white hover:bg-green-600">
                  <Plus className="h-4 w-4" />
                </Button>
              </div>
              {formData.crops_grown.length > 0 ? (
                <div className="space-y-2">
                  {formData.crops_grown.map((crop) => (
                    <div
                      key={crop}
                      className="flex items-center justify-between rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-sm"
                    >
                      <span className="font-medium text-green-800">{crop}</span>
                      <button
                        type="button"
                        onClick={() => removeCrop(crop)}
                        className="inline-flex h-8 w-8 items-center justify-center rounded-md text-red-600 hover:bg-red-50 hover:text-red-700"
                        aria-label={copy.removeCrop(crop)}
                      >
                        <X className="h-4 w-4" />
                      </button>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-muted">{copy.addAtLeastOneCrop}</p>
              )}
            </div>

            {error ? (
              <div className="rounded-[var(--radius)] border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                {error}
              </div>
            ) : null}

            <div className="grid grid-cols-1 gap-4 pt-2 sm:grid-cols-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => navigate("/onboarding/language")}
                className="h-12 rounded-2xl border-green-200 bg-white text-base font-semibold text-green-700 transition-all duration-200 hover:-translate-y-0.5 hover:bg-green-50"
              >
                <ArrowLeft className="mr-2 h-4 w-4" />
                {copy.back}
              </Button>
              <Button
                type="button"
                onClick={handleSubmit}
                disabled={isLoading}
                className="h-12 rounded-2xl bg-green-500 px-5 text-base font-semibold text-white transition-all duration-200 hover:-translate-y-0.5 hover:bg-green-600"
              >
                {isLoading ? copy.saving : copy.complete}
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
