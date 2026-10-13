import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle,
  KeyRound,
  Leaf,
  Loader2,
  LogOut,
  Plus,
  Save,
  ShieldCheck,
  Trash2,
  X,
} from "lucide-react";
import { accountApi } from "@/lib/account";
import { extractErrorMessage } from "@/lib/errors";
import { profileApi } from "@/lib/profile";
import { useAuth } from "@/contexts/AuthContext";
import { useLanguage } from "@/contexts/LanguageContext";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

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
    chat: "Chat",
    signOut: "Sign out",
    title: "Settings",
    subtitle: "Manage the farming profile Farmly uses for advice.",
    farmingProfile: "Farming Profile",
    fullName: "Full Name",
    phoneNumber: "Phone Number",
    location: "Location",
    locationPlaceholder: "Example: 9.03,38.74",
    language: "Language",
    english: "English",
    amharic: "Amharic",
    experience: "Experience",
    years: "Years",
    mainGoal: "Main Goal",
    cropsGrown: "Crops Grown",
    addCrop: "Add crop",
    removeCrop: (crop) => `Remove ${crop}`,
    saveProfile: "Save profile",
    savingProfile: "Saving profile...",
    phoneChange: "Phone Change",
    currentPassword: "Current Password",
    newPhoneNumber: "New Phone Number",
    phonePlaceholder: "0911xxxxxx or 2519xxxxxxxx",
    otpCode: "OTP Code",
    debugOtp: "Debug OTP",
    requestOtp: "Request OTP",
    confirmChange: "Confirm change",
    cancel: "Cancel",
    dangerZone: "Danger Zone",
    dangerText:
      "Delete your Farmly account permanently. This removes your profile, chats, messages, alerts, and account access. This action cannot be undone.",
    deleteAccount: "Delete account",
    deleteConfirm: "This will permanently delete your Farmly account and all related data. Continue?",
    loadProfileError: "Could not load profile.",
    profileInvalid: "Please complete all profile fields and keep at least one crop.",
    profileSaved: "Profile updated successfully.",
    profileSaveError: "Could not update profile.",
    phoneOtpSent: "OTP sent to the new phone number.",
    phoneOtpSentDebug: (otp) => `OTP sent. Debug OTP: ${otp}`,
    phoneRequestError: "Could not request phone change.",
    phoneChanged: "Phone number changed successfully.",
    phoneConfirmError: "Could not confirm phone change.",
    deleteError: "Could not delete account.",
  },
  am: {
    chat: "ውይይት",
    signOut: "ውጣ",
    title: "ቅንብሮች",
    subtitle: "Farmly ለምክር የሚጠቀምበትን የእርሻ መገለጫ ያስተዳድሩ።",
    farmingProfile: "የእርሻ መገለጫ",
    fullName: "ሙሉ ስም",
    phoneNumber: "ስልክ ቁጥር",
    location: "ቦታ",
    locationPlaceholder: "ምሳሌ፦ 9.03,38.74",
    language: "ቋንቋ",
    english: "እንግሊዝኛ",
    amharic: "አማርኛ",
    experience: "ልምድ",
    years: "ዓመታት",
    mainGoal: "ዋና ግብ",
    cropsGrown: "የሚያበቅሏቸው ሰብሎች",
    addCrop: "ሰብል ያክሉ",
    removeCrop: (crop) => `${crop} አስወግድ`,
    saveProfile: "መገለጫ አስቀምጥ",
    savingProfile: "መገለጫ በማስቀመጥ ላይ...",
    phoneChange: "ስልክ ቁጥር መቀየር",
    currentPassword: "የአሁኑ የይለፍ ቃል",
    newPhoneNumber: "አዲስ ስልክ ቁጥር",
    phonePlaceholder: "0911xxxxxx ወይም 2519xxxxxxxx",
    otpCode: "የOTP ኮድ",
    debugOtp: "የሙከራ OTP",
    requestOtp: "OTP ጠይቅ",
    confirmChange: "ለውጡን አረጋግጥ",
    cancel: "ሰርዝ",
    dangerZone: "አደገኛ ክፍል",
    dangerText:
      "የFarmly መለያዎን በቋሚነት ያጠፋል። መገለጫ፣ ውይይቶች፣ መልዕክቶች፣ አስጠንቅቂያዎች እና የመለያ መዳረሻ ይጠፋሉ። ይህ ተግባር መመለስ አይቻልም።",
    deleteAccount: "መለያ አጥፋ",
    deleteConfirm: "የFarmly መለያዎን እና ሁሉንም ተዛማጅ መረጃ በቋሚነት ያጠፋል። መቀጠል ይፈልጋሉ?",
    loadProfileError: "መገለጫ መጫን አልተቻለም።",
    profileInvalid: "እባክዎ ሁሉንም የመገለጫ መስኮች ይሙሉ እና ቢያንስ አንድ ሰብል ያስቀምጡ።",
    profileSaved: "መገለጫ ተዘምኗል።",
    profileSaveError: "መገለጫ ማዘመን አልተቻለም።",
    phoneOtpSent: "OTP ወደ አዲሱ ስልክ ቁጥር ተልኳል።",
    phoneOtpSentDebug: (otp) => `OTP ተልኳል። የሙከራ OTP: ${otp}`,
    phoneRequestError: "ስልክ ቁጥር መቀየር መጠየቅ አልተቻለም።",
    phoneChanged: "ስልክ ቁጥሩ ተቀይሯል።",
    phoneConfirmError: "ስልክ ቁጥር መቀየር ማረጋገጥ አልተቻለም።",
    deleteError: "መለያ ማጥፋት አልተቻለም።",
  },
};

const initialProfileForm = {
  full_name: "",
  location: "",
  preferred_language: "en",
  user_type: "beginner",
  years_experience: "0",
  main_goal: "increase_yield",
  crops_grown: [],
};

function SelectField({ id, value, onChange, children }) {
  return (
    <select
      id={id}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      className="h-10 w-full rounded-[var(--radius)] border border-border bg-card px-3 text-sm text-foreground outline-none focus:border-primary"
    >
      {children}
    </select>
  );
}

function StatusMessage({ type, children }) {
  if (!children) return null;
  const styles =
    type === "error"
      ? "border-red-200 bg-red-50 text-red-700"
      : "border-green-200 bg-green-50 text-green-700";

  return <div className={`rounded-[var(--radius)] border px-3 py-2 text-sm ${styles}`}>{children}</div>;
}

export default function SettingsPage() {
  const navigate = useNavigate();
  const { accessToken, clearToken, isHydrated } = useAuth();
  const { language, setLanguage } = useLanguage();
  const copy = COPY[language] || COPY.en;
  const [loading, setLoading] = useState(true);
  const [savingProfile, setSavingProfile] = useState(false);
  const [profileError, setProfileError] = useState("");
  const [profileSuccess, setProfileSuccess] = useState("");
  const [phoneNumber, setPhoneNumber] = useState("");
  const [cropInput, setCropInput] = useState("");
  const [profileForm, setProfileForm] = useState(initialProfileForm);

  const [phoneChange, setPhoneChange] = useState({
    current_password: "",
    new_phone_number: "",
    otp_code: "",
  });
  const [phoneRequestSent, setPhoneRequestSent] = useState(false);
  const [phoneDebugOtp, setPhoneDebugOtp] = useState(null);
  const [phoneLoading, setPhoneLoading] = useState(false);
  const [phoneError, setPhoneError] = useState("");
  const [phoneSuccess, setPhoneSuccess] = useState("");
  const [deleteAccount, setDeleteAccount] = useState({
    current_password: "",
  });
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [deleteError, setDeleteError] = useState("");

  useEffect(() => {
    if (!isHydrated) return;
    if (!accessToken) {
      navigate("/auth-options", { replace: true });
      return;
    }

    loadProfile();
  }, [accessToken, isHydrated, navigate]);

  async function loadProfile() {
    setLoading(true);
    setProfileError("");
    try {
      const { data } = await profileApi.getProfile();
      setPhoneNumber(data.phone_number || "");
      setProfileForm({
        full_name: data.full_name || "",
        location: data.location || "",
        preferred_language: data.preferred_language || "en",
        user_type: data.user_type || "beginner",
        years_experience: String(data.years_experience ?? 0),
        main_goal: data.main_goal || "increase_yield",
        crops_grown: Array.isArray(data.crops_grown) ? data.crops_grown : [],
      });
    } catch (error) {
      setProfileError(extractErrorMessage(error, copy.loadProfileError));
    } finally {
      setLoading(false);
    }
  }

  const profileIsValid = useMemo(
    () =>
      profileForm.full_name.trim().length >= 2 &&
      profileForm.location.trim().length >= 2 &&
      profileForm.preferred_language.trim().length >= 2 &&
      profileForm.user_type &&
      profileForm.main_goal &&
      profileForm.crops_grown.length > 0 &&
      Number(profileForm.years_experience) >= 0 &&
      Number(profileForm.years_experience) <= 80,
    [profileForm]
  );

  function addCrop() {
    const normalized = cropInput.trim().toLowerCase();
    if (!normalized) return;
    setProfileForm((previous) => {
      if (previous.crops_grown.includes(normalized)) return previous;
      return { ...previous, crops_grown: [...previous.crops_grown, normalized] };
    });
    setCropInput("");
  }

  function removeCrop(crop) {
    setProfileForm((previous) => ({
      ...previous,
      crops_grown: previous.crops_grown.filter((item) => item !== crop),
    }));
  }

  async function handleProfileSave() {
    if (!profileIsValid) {
      setProfileError(copy.profileInvalid);
      return;
    }

    setSavingProfile(true);
    setProfileError("");
    setProfileSuccess("");
    try {
      const payload = {
        full_name: profileForm.full_name.trim(),
        location: profileForm.location.trim(),
        preferred_language: profileForm.preferred_language,
        user_type: profileForm.user_type,
        years_experience: Number(profileForm.years_experience),
        main_goal: profileForm.main_goal,
        crops_grown: profileForm.crops_grown,
      };
      await profileApi.updateProfile(payload);
      setProfileSuccess(copy.profileSaved);
    } catch (error) {
      setProfileError(extractErrorMessage(error, copy.profileSaveError));
    } finally {
      setSavingProfile(false);
    }
  }

  async function handleRequestPhoneChange() {
    setPhoneLoading(true);
    setPhoneError("");
    setPhoneSuccess("");
    setPhoneDebugOtp(null);
    try {
      const { data } = await accountApi.requestPhoneChange(phoneChange);
      setPhoneRequestSent(true);
      setPhoneDebugOtp(data.debug_otp || null);
      setPhoneSuccess(data.debug_otp ? copy.phoneOtpSentDebug(data.debug_otp) : copy.phoneOtpSent);
    } catch (error) {
      setPhoneError(extractErrorMessage(error, copy.phoneRequestError));
    } finally {
      setPhoneLoading(false);
    }
  }

  async function handleConfirmPhoneChange() {
    setPhoneLoading(true);
    setPhoneError("");
    setPhoneSuccess("");
    try {
      const { data } = await accountApi.confirmPhoneChange(phoneChange);
      setPhoneNumber(data.phone_number);
      setPhoneSuccess(copy.phoneChanged);
      setPhoneRequestSent(false);
      setPhoneDebugOtp(null);
      setPhoneChange({ current_password: "", new_phone_number: "", otp_code: "" });
      await loadProfile();
    } catch (error) {
      setPhoneError(extractErrorMessage(error, copy.phoneConfirmError));
    } finally {
      setPhoneLoading(false);
    }
  }

  function handleSignOut() {
    clearToken();
    navigate("/auth-options", { replace: true });
  }

  async function handleDeleteAccount() {
    if (!confirm(copy.deleteConfirm)) {
      return;
    }

    setDeleteLoading(true);
    setDeleteError("");
    try {
      await accountApi.deleteAccount({
        current_password: deleteAccount.current_password,
      });
      clearToken();
      navigate("/", { replace: true });
    } catch (error) {
      setDeleteError(extractErrorMessage(error, copy.deleteError));
    } finally {
      setDeleteLoading(false);
    }
  }

  if (!isHydrated || loading) {
    return (
      <main className="grid min-h-screen place-items-center bg-background">
        <Loader2 className="h-7 w-7 animate-spin text-primary" />
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-background">
      <header className="border-b border-border bg-card">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-4 sm:px-6">
          <Link to="/main-page" className="inline-flex items-center gap-2 text-sm font-medium text-muted-foreground hover:text-foreground">
            <ArrowLeft className="h-4 w-4" />
            {copy.chat}
          </Link>
          <Button variant="ghost" onClick={handleSignOut} className="gap-2 text-red-600 hover:text-red-700">
            <LogOut className="h-4 w-4" />
            {copy.signOut}
          </Button>
        </div>
      </header>

      <div className="mx-auto grid max-w-5xl gap-5 px-4 py-6 sm:px-6 lg:grid-cols-[1.4fr_1fr]">
        <section className="space-y-5">
          <div>
            <h1 className="text-2xl font-bold text-foreground">{copy.title}</h1>
            <p className="mt-1 text-sm text-muted-foreground">{copy.subtitle}</p>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Leaf className="h-5 w-5 text-primary" />
                {copy.farmingProfile}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <Label htmlFor="full_name">{copy.fullName}</Label>
                  <Input
                    id="full_name"
                    value={profileForm.full_name}
                    onChange={(event) => setProfileForm((previous) => ({ ...previous, full_name: event.target.value }))}
                  />
                </div>
                <div>
                  <Label htmlFor="phone_number">{copy.phoneNumber}</Label>
                  <Input id="phone_number" value={phoneNumber} disabled className="bg-gray-50 text-muted-foreground" />
                </div>
              </div>

              <div>
                <Label htmlFor="location">{copy.location}</Label>
                <Input
                  id="location"
                  value={profileForm.location}
                  placeholder={copy.locationPlaceholder}
                  onChange={(event) => setProfileForm((previous) => ({ ...previous, location: event.target.value }))}
                />
              </div>

              <div className="grid gap-4 sm:grid-cols-3">
                <div>
                  <Label htmlFor="preferred_language">{copy.language}</Label>
                  <SelectField
                    id="preferred_language"
                    value={profileForm.preferred_language}
                    onChange={(value) => {
                      setProfileForm((previous) => ({ ...previous, preferred_language: value }));
                      setLanguage(value);
                    }}
                  >
                    <option value="en">{copy.english}</option>
                    <option value="am">{copy.amharic}</option>
                  </SelectField>
                </div>
                <div>
                  <Label htmlFor="user_type">{copy.experience}</Label>
                  <SelectField
                    id="user_type"
                    value={profileForm.user_type}
                    onChange={(value) => setProfileForm((previous) => ({ ...previous, user_type: value }))}
                  >
                    {USER_TYPE_OPTIONS.map((item) => (
                      <option key={item.value} value={item.value}>
                        {item.label[language] || item.label.en}
                      </option>
                    ))}
                  </SelectField>
                </div>
                <div>
                  <Label htmlFor="years_experience">{copy.years}</Label>
                  <Input
                    id="years_experience"
                    type="number"
                    min="0"
                    max="80"
                    value={profileForm.years_experience}
                    onChange={(event) => setProfileForm((previous) => ({ ...previous, years_experience: event.target.value }))}
                  />
                </div>
              </div>

              <div>
                <Label htmlFor="main_goal">{copy.mainGoal}</Label>
                <SelectField
                  id="main_goal"
                  value={profileForm.main_goal}
                  onChange={(value) => setProfileForm((previous) => ({ ...previous, main_goal: value }))}
                >
                  {MAIN_GOAL_OPTIONS.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label[language] || item.label.en}
                    </option>
                  ))}
                </SelectField>
              </div>

              <div className="space-y-3">
                <Label htmlFor="crop_input">{copy.cropsGrown}</Label>
                <div className="flex gap-2">
                  <Input
                    id="crop_input"
                    value={cropInput}
                    placeholder={copy.addCrop}
                    onChange={(event) => setCropInput(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") {
                        event.preventDefault();
                        addCrop();
                      }
                    }}
                  />
                  <Button onClick={addCrop} size="icon" aria-label={copy.addCrop}>
                    <Plus className="h-4 w-4" />
                  </Button>
                </div>
                <div className="flex flex-wrap gap-2">
                  {profileForm.crops_grown.map((crop) => (
                    <span key={crop} className="inline-flex items-center gap-2 rounded-full border border-green-200 bg-green-50 px-3 py-1 text-sm text-green-800">
                      {crop}
                      <button
                        type="button"
                        onClick={() => removeCrop(crop)}
                        aria-label={copy.removeCrop(crop)}
                        className="inline-flex h-8 w-8 items-center justify-center rounded-md hover:bg-green-100"
                      >
                        <X className="h-3.5 w-3.5" />
                      </button>
                    </span>
                  ))}
                </div>
              </div>

              <StatusMessage type="error">{profileError}</StatusMessage>
              <StatusMessage type="success">{profileSuccess}</StatusMessage>

              <Button onClick={handleProfileSave} disabled={savingProfile || !profileIsValid} className="w-full gap-2 sm:w-auto">
                {savingProfile ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                {savingProfile ? copy.savingProfile : copy.saveProfile}
              </Button>
            </CardContent>
          </Card>
        </section>

        <aside className="space-y-5">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <ShieldCheck className="h-5 w-5 text-primary" />
                {copy.phoneChange}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label htmlFor="current_password">{copy.currentPassword}</Label>
                <Input
                  id="current_password"
                  type="password"
                  value={phoneChange.current_password}
                  onChange={(event) => setPhoneChange((previous) => ({ ...previous, current_password: event.target.value }))}
                />
              </div>
              <div>
                <Label htmlFor="new_phone_number">{copy.newPhoneNumber}</Label>
                <Input
                  id="new_phone_number"
                  placeholder={copy.phonePlaceholder}
                  value={phoneChange.new_phone_number}
                  onChange={(event) => setPhoneChange((previous) => ({ ...previous, new_phone_number: event.target.value }))}
                />
              </div>
              {phoneRequestSent && (
                <div>
                  <Label htmlFor="otp_code">{copy.otpCode}</Label>
                  <Input
                    id="otp_code"
                    value={phoneChange.otp_code}
                    onChange={(event) => setPhoneChange((previous) => ({ ...previous, otp_code: event.target.value }))}
                  />
                </div>
              )}

              {phoneDebugOtp && (
                <div className="rounded-[var(--radius)] border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
                  {copy.debugOtp}: <span className="font-semibold">{phoneDebugOtp}</span>
                </div>
              )}

              <StatusMessage type="error">{phoneError}</StatusMessage>
              <StatusMessage type="success">{phoneSuccess}</StatusMessage>

              {!phoneRequestSent ? (
                <Button
                  onClick={handleRequestPhoneChange}
                  disabled={phoneLoading || phoneChange.current_password.length < 8 || phoneChange.new_phone_number.trim().length < 9}
                  className="w-full gap-2"
                >
                  {phoneLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <KeyRound className="h-4 w-4" />}
                  {copy.requestOtp}
                </Button>
              ) : (
                <div className="grid gap-2">
                  <Button
                    onClick={handleConfirmPhoneChange}
                    disabled={phoneLoading || phoneChange.otp_code.trim().length < 4}
                    className="w-full gap-2"
                  >
                    {phoneLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle className="h-4 w-4" />}
                    {copy.confirmChange}
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => {
                      setPhoneRequestSent(false);
                      setPhoneDebugOtp(null);
                      setPhoneError("");
                      setPhoneSuccess("");
                    }}
                    className="w-full gap-2"
                  >
                    <Trash2 className="h-4 w-4" />
                    {copy.cancel}
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="border-red-200 bg-red-50/50">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-red-700">
                <AlertTriangle className="h-5 w-5" />
                {copy.dangerZone}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm leading-6 text-red-700">
                {copy.dangerText}
              </p>

              <div>
                <Label htmlFor="delete_current_password">{copy.currentPassword}</Label>
                <Input
                  id="delete_current_password"
                  type="password"
                  value={deleteAccount.current_password}
                  onChange={(event) =>
                    setDeleteAccount((previous) => ({
                      ...previous,
                      current_password: event.target.value,
                    }))
                  }
                />
              </div>

              <StatusMessage type="error">{deleteError}</StatusMessage>

              <Button
                variant="outline"
                onClick={handleDeleteAccount}
                disabled={
                  deleteLoading ||
                  deleteAccount.current_password.length < 8
                }
                className="w-full gap-2 border-red-300 bg-white text-red-700 hover:bg-red-100"
              >
                {deleteLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
                {copy.deleteAccount}
              </Button>
            </CardContent>
          </Card>
        </aside>
      </div>
    </main>
  );
}
