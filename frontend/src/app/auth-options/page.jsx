import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Eye, EyeOff } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { useLanguage } from "@/contexts/LanguageContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const COPY = {
  en: {
    genericError: "Something went wrong. Please try again.",
    title: "Farmly Authentication",
    signIn: "Sign In",
    signUp: "Sign Up",
    phoneNumber: "Phone Number",
    password: "Password",
    fullName: "Full Name",
    otpCode: "OTP Code",
    confirmPassword: "Confirm Password",
    newPassword: "New Password",
    confirmNewPassword: "Confirm New Password",
    phonePlaceholder: "0911xxxxxx or 2519xxxxxxxx",
    namePlaceholder: "Enter your full name",
    passwordPlaceholder: "Minimum 8 characters",
    confirmPasswordPlaceholder: "Re-enter your password",
    confirmNewPasswordPlaceholder: "Re-enter new password",
    otpPlaceholder: "Enter OTP code",
    signingIn: "Signing in...",
    requestingOtp: "Requesting OTP...",
    requestOtp: "Request OTP",
    sending: "Sending...",
    resendOtp: "Resend OTP",
    verifying: "Verifying...",
    verifyOtp: "Verify OTP",
    settingPassword: "Setting Password...",
    setPasswordContinue: "Set Password & Continue",
    startOver: "Start Over",
    forgotPassword: "Forgot password?",
    resetPassword: "Reset Password",
    resetIntro: "Enter your registered phone number to receive a reset code.",
    resetOtpIntro: "Enter the OTP code sent to your phone.",
    resetNewPasswordIntro: "Set your new password.",
    sendResetCode: "Send Reset Code",
    resend: "Resend",
    verify: "Verify",
    resetting: "Resetting...",
    resetPasswordButton: "Reset Password",
    backToSignIn: "Back to Sign In",
    passwordMismatch: "Passwords do not match.",
    debugOtp: "Debug OTP",
    otpSentDebug: (otp) => `OTP sent. Debug OTP: ${otp}`,
    otpSent: "OTP sent successfully. Please check your phone.",
    otpVerified: "OTP verified. Set your password to complete account setup.",
    resetOtpSent: "OTP sent to your phone number.",
    resetOtpVerified: "OTP verified. Set your new password.",
    resetSuccess: "Password reset successfully. You can now sign in.",
  },
  am: {
    genericError: "ችግር ተፈጥሯል። እባክዎ እንደገና ይሞክሩ።",
    title: "የFarmly መግቢያ",
    signIn: "ግባ",
    signUp: "መዝገብ",
    phoneNumber: "ስልክ ቁጥር",
    password: "የይለፍ ቃል",
    fullName: "ሙሉ ስም",
    otpCode: "የOTP ኮድ",
    confirmPassword: "የይለፍ ቃል ያረጋግጡ",
    newPassword: "አዲስ የይለፍ ቃል",
    confirmNewPassword: "አዲሱን የይለፍ ቃል ያረጋግጡ",
    phonePlaceholder: "0911xxxxxx ወይም 2519xxxxxxxx",
    namePlaceholder: "ሙሉ ስምዎን ያስገቡ",
    passwordPlaceholder: "ቢያንስ 8 ፊደላት",
    confirmPasswordPlaceholder: "የይለፍ ቃሉን እንደገና ያስገቡ",
    confirmNewPasswordPlaceholder: "አዲሱን የይለፍ ቃል እንደገና ያስገቡ",
    otpPlaceholder: "የOTP ኮድ ያስገቡ",
    signingIn: "በመግባት ላይ...",
    requestingOtp: "OTP በመጠየቅ ላይ...",
    requestOtp: "OTP ጠይቅ",
    sending: "በመላክ ላይ...",
    resendOtp: "OTP እንደገና ላክ",
    verifying: "በማረጋገጥ ላይ...",
    verifyOtp: "OTP አረጋግጥ",
    settingPassword: "የይለፍ ቃል በማስቀመጥ ላይ...",
    setPasswordContinue: "የይለፍ ቃል አስቀምጥ እና ቀጥል",
    startOver: "እንደገና ጀምር",
    forgotPassword: "የይለፍ ቃል ረሱ?",
    resetPassword: "የይለፍ ቃል ቀይር",
    resetIntro: "የመቀየሪያ ኮድ ለመቀበል የተመዘገበውን ስልክ ቁጥር ያስገቡ።",
    resetOtpIntro: "ወደ ስልክዎ የተላከውን OTP ኮድ ያስገቡ።",
    resetNewPasswordIntro: "አዲሱን የይለፍ ቃል ያስቀምጡ።",
    sendResetCode: "የመቀየሪያ ኮድ ላክ",
    resend: "እንደገና ላክ",
    verify: "አረጋግጥ",
    resetting: "በመቀየር ላይ...",
    resetPasswordButton: "የይለፍ ቃል ቀይር",
    backToSignIn: "ወደ መግቢያ ተመለስ",
    passwordMismatch: "የይለፍ ቃሎቹ አይመሳሰሉም።",
    debugOtp: "የሙከራ OTP",
    otpSentDebug: (otp) => `OTP ተልኳል። የሙከራ OTP: ${otp}`,
    otpSent: "OTP ተልኳል። እባክዎ ስልክዎን ይመልከቱ።",
    otpVerified: "OTP ተረጋግጧል። መለያዎን ለማጠናቀቅ የይለፍ ቃል ያስቀምጡ።",
    resetOtpSent: "OTP ወደ ስልክ ቁጥርዎ ተልኳል።",
    resetOtpVerified: "OTP ተረጋግጧል። አዲስ የይለፍ ቃል ያስቀምጡ።",
    resetSuccess: "የይለፍ ቃል ተቀይሯል። አሁን መግባት ይችላሉ።",
  },
};

function extractErrorMessage(error, fallback = "Something went wrong. Please try again.") {
  const detail = error?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const msgs = detail.map((d) => d?.msg).filter(Boolean);
    if (msgs.length) return msgs.join(", ");
  }
  return error?.message || fallback;
}

function PasswordInput({ id, placeholder, value, onChange }) {
  const [show, setShow] = useState(false);
  return (
    <div className="relative">
      <Input
        id={id}
        type={show ? "text" : "password"}
        placeholder={placeholder}
        value={value}
        onChange={onChange}
        className="pr-10"
      />
      <button
        type="button"
        onClick={() => setShow((v) => !v)}
        className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
        tabIndex={-1}
      >
        {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
      </button>
    </div>
  );
}

export default function AuthOptionsPage() {
  const navigate = useNavigate();
  const { accessToken, isHydrated, setToken } = useAuth();
  const { language } = useLanguage();
  const copy = COPY[language] || COPY.en;

  const [mode, setMode] = useState("signin");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const [signinData, setSigninData] = useState({ phone_number: "", password: "" });

  const [signupStep, setSignupStep] = useState(1);
  const [signupData, setSignupData] = useState({
    full_name: "",
    phone_number: "",
    otp_code: "",
    setup_token: "",
    password: "",
    confirm_password: "",
  });
  const [debugOtp, setDebugOtp] = useState(null);

  const [forgotStep, setForgotStep] = useState(1);
  const [forgotData, setForgotData] = useState({
    phone_number: "",
    otp_code: "",
    reset_token: "",
    new_password: "",
    confirm_password: "",
  });
  const [forgotDebugOtp, setForgotDebugOtp] = useState(null);

  useEffect(() => {
    if (isHydrated && accessToken) {
      navigate("/main-page", { replace: true });
    }
  }, [accessToken, isHydrated, navigate]);

  const canSubmitSignIn = useMemo(
    () => signinData.phone_number.trim().length >= 9 && signinData.password.length >= 8,
    [signinData]
  );

  const canSubmitRequestOtp = useMemo(
    () => signupData.full_name.trim().length >= 2 && signupData.phone_number.trim().length >= 9,
    [signupData]
  );

  const canSubmitVerifyOtp = useMemo(() => signupData.otp_code.trim().length >= 4, [signupData]);

  const canSubmitSetPassword = useMemo(
    () =>
      signupData.password.length >= 8 &&
      signupData.confirm_password.length >= 8 &&
      signupData.password === signupData.confirm_password,
    [signupData]
  );

  function switchMode(next) {
    setMode(next);
    setError("");
    setSuccess("");
  }

  async function handleLogin() {
    if (!canSubmitSignIn) return;
    setIsLoading(true);
    setError("");
    setSuccess("");
    try {
      const { data } = await api.post("/api/auth/login", {
        phone_number: signinData.phone_number,
        password: signinData.password,
      });
      setToken(data.access_token);
      navigate(data?.user?.onboarding_completed ? "/main-page" : "/onboarding/location");
    } catch (err) {
      setError(extractErrorMessage(err, copy.genericError));
    } finally {
      setIsLoading(false);
    }
  }

  async function handleRequestOtp() {
    if (!canSubmitRequestOtp) return;
    setIsLoading(true);
    setError("");
    setSuccess("");
    try {
      const { data } = await api.post("/api/auth/request-otp", {
        full_name: signupData.full_name,
        phone_number: signupData.phone_number,
      });
      setDebugOtp(data.debug_otp || null);
      setSignupStep(2);
      setSuccess(data.debug_otp ? copy.otpSentDebug(data.debug_otp) : copy.otpSent);
    } catch (err) {
      setError(extractErrorMessage(err, copy.genericError));
    } finally {
      setIsLoading(false);
    }
  }

  async function handleVerifyOtp() {
    if (!canSubmitVerifyOtp) return;
    setIsLoading(true);
    setError("");
    setSuccess("");
    try {
      const { data } = await api.post("/api/auth/verify-otp", {
        phone_number: signupData.phone_number,
        otp_code: signupData.otp_code,
      });
      setSignupData((prev) => ({ ...prev, setup_token: data.setup_token }));
      setSignupStep(3);
      setSuccess(copy.otpVerified);
    } catch (err) {
      setError(extractErrorMessage(err, copy.genericError));
    } finally {
      setIsLoading(false);
    }
  }

  async function handleSetPassword() {
    if (!canSubmitSetPassword) return;
    setIsLoading(true);
    setError("");
    setSuccess("");
    try {
      const { data } = await api.post("/api/auth/set-password", {
        phone_number: signupData.phone_number,
        setup_token: signupData.setup_token,
        password: signupData.password,
      });
      setToken(data.access_token);
      navigate("/onboarding/location");
    } catch (err) {
      setError(extractErrorMessage(err, copy.genericError));
    } finally {
      setIsLoading(false);
    }
  }

  function resetSignupFlow() {
    setSignupStep(1);
    setDebugOtp(null);
    setSignupData({ full_name: "", phone_number: "", otp_code: "", setup_token: "", password: "", confirm_password: "" });
    setError("");
    setSuccess("");
  }

  async function handleForgotRequestOtp() {
    setIsLoading(true);
    setError("");
    setSuccess("");
    try {
      const { data } = await api.post("/api/auth/forgot-password", {
        phone_number: forgotData.phone_number,
      });
      setForgotDebugOtp(data.debug_otp || null);
      setForgotStep(2);
      setSuccess(data.debug_otp ? copy.otpSentDebug(data.debug_otp) : copy.resetOtpSent);
    } catch (err) {
      setError(extractErrorMessage(err, copy.genericError));
    } finally {
      setIsLoading(false);
    }
  }

  async function handleForgotVerifyOtp() {
    setIsLoading(true);
    setError("");
    setSuccess("");
    try {
      const { data } = await api.post("/api/auth/forgot-password/verify", {
        phone_number: forgotData.phone_number,
        otp_code: forgotData.otp_code,
      });
      setForgotData((prev) => ({ ...prev, reset_token: data.setup_token }));
      setForgotStep(3);
      setSuccess(copy.resetOtpVerified);
    } catch (err) {
      setError(extractErrorMessage(err, copy.genericError));
    } finally {
      setIsLoading(false);
    }
  }

  async function handleResetPassword() {
    setIsLoading(true);
    setError("");
    setSuccess("");
    try {
      await api.post("/api/auth/reset-password", {
        phone_number: forgotData.phone_number,
        reset_token: forgotData.reset_token,
        new_password: forgotData.new_password,
        confirm_password: forgotData.confirm_password,
      });
      setSuccess(copy.resetSuccess);
      setTimeout(() => {
        setForgotStep(1);
        setForgotData({ phone_number: "", otp_code: "", reset_token: "", new_password: "", confirm_password: "" });
        setForgotDebugOtp(null);
        switchMode("signin");
      }, 1500);
    } catch (err) {
      setError(extractErrorMessage(err, copy.genericError));
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-background px-4 py-10 sm:px-6 sm:py-14">
      <div className="mx-auto w-full max-w-md">
        <Card>
          <CardHeader>
            <CardTitle className="text-xl sm:text-2xl">{copy.title}</CardTitle>
          </CardHeader>
          <CardContent>
            {mode !== "forgot" && (
              <div className="mb-6 grid grid-cols-2 gap-2 rounded-[var(--radius)] border border-border p-1">
                <Button
                  variant={mode === "signin" ? "primary" : "ghost"}
                  size="sm"
                  onClick={() => switchMode("signin")}
                >
                  {copy.signIn}
                </Button>
                <Button
                  variant={mode === "signup" ? "primary" : "ghost"}
                  size="sm"
                  onClick={() => switchMode("signup")}
                >
                  {copy.signUp}
                </Button>
              </div>
            )}

            {mode === "signin" && (
              <div className="space-y-4">
                <div>
                  <Label htmlFor="signin-phone">{copy.phoneNumber}</Label>
                  <Input
                    id="signin-phone"
                    placeholder={copy.phonePlaceholder}
                    value={signinData.phone_number}
                    onChange={(e) => setSigninData((prev) => ({ ...prev, phone_number: e.target.value }))}
                  />
                </div>
                <div>
                  <Label htmlFor="signin-password">{copy.password}</Label>
                  <PasswordInput
                    id="signin-password"
                    placeholder={copy.passwordPlaceholder}
                    value={signinData.password}
                    onChange={(e) => setSigninData((prev) => ({ ...prev, password: e.target.value }))}
                  />
                </div>
                <Button className="w-full" onClick={handleLogin} disabled={isLoading || !canSubmitSignIn}>
                  {isLoading ? copy.signingIn : copy.signIn}
                </Button>
                <button
                  type="button"
                  className="w-full text-center text-xs text-muted-foreground hover:text-foreground underline"
                  onClick={() => switchMode("forgot")}
                >
                  {copy.forgotPassword}
                </button>
              </div>
            )}

            {mode === "signup" && (
              <div className="space-y-4">
                {signupStep === 1 && (
                  <>
                    <div>
                      <Label htmlFor="signup-name">{copy.fullName}</Label>
                      <Input
                        id="signup-name"
                        placeholder={copy.namePlaceholder}
                        value={signupData.full_name}
                        onChange={(e) => setSignupData((prev) => ({ ...prev, full_name: e.target.value }))}
                      />
                    </div>
                    <div>
                      <Label htmlFor="signup-phone">{copy.phoneNumber}</Label>
                      <Input
                        id="signup-phone"
                        placeholder={copy.phonePlaceholder}
                        value={signupData.phone_number}
                        onChange={(e) => setSignupData((prev) => ({ ...prev, phone_number: e.target.value }))}
                      />
                    </div>
                    <Button className="w-full" onClick={handleRequestOtp} disabled={isLoading || !canSubmitRequestOtp}>
                      {isLoading ? copy.requestingOtp : copy.requestOtp}
                    </Button>
                  </>
                )}

                {signupStep === 2 && (
                  <>
                    <div>
                      <Label htmlFor="signup-otp">{copy.otpCode}</Label>
                      <Input
                        id="signup-otp"
                        placeholder={copy.otpPlaceholder}
                        value={signupData.otp_code}
                        onChange={(e) => setSignupData((prev) => ({ ...prev, otp_code: e.target.value }))}
                      />
                    </div>
                    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                      <Button variant="outline" onClick={handleRequestOtp} disabled={isLoading}>
                        {isLoading ? copy.sending : copy.resendOtp}
                      </Button>
                      <Button onClick={handleVerifyOtp} disabled={isLoading || !canSubmitVerifyOtp}>
                        {isLoading ? copy.verifying : copy.verifyOtp}
                      </Button>
                    </div>
                    {debugOtp && (
                      <p className="text-xs text-muted">
                        {copy.debugOtp}: <span className="font-semibold">{debugOtp}</span>
                      </p>
                    )}
                  </>
                )}

                {signupStep === 3 && (
                  <>
                    <div>
                      <Label htmlFor="signup-password">{copy.password}</Label>
                      <PasswordInput
                        id="signup-password"
                        placeholder={copy.passwordPlaceholder}
                        value={signupData.password}
                        onChange={(e) => setSignupData((prev) => ({ ...prev, password: e.target.value }))}
                      />
                    </div>
                    <div>
                      <Label htmlFor="signup-confirm-password">{copy.confirmPassword}</Label>
                      <PasswordInput
                        id="signup-confirm-password"
                        placeholder={copy.confirmPasswordPlaceholder}
                        value={signupData.confirm_password}
                        onChange={(e) => setSignupData((prev) => ({ ...prev, confirm_password: e.target.value }))}
                      />
                    </div>
                    {signupData.password && signupData.confirm_password && signupData.password !== signupData.confirm_password && (
                      <p className="text-xs text-red-600">{copy.passwordMismatch}</p>
                    )}
                    <Button className="w-full" onClick={handleSetPassword} disabled={isLoading || !canSubmitSetPassword}>
                      {isLoading ? copy.settingPassword : copy.setPasswordContinue}
                    </Button>
                  </>
                )}

                {signupStep > 1 && (
                  <Button variant="ghost" className="w-full" onClick={resetSignupFlow}>
                    {copy.startOver}
                  </Button>
                )}
              </div>
            )}

            {mode === "forgot" && (
              <div className="space-y-4">
                <div className="mb-2">
                  <h2 className="text-base font-semibold">{copy.resetPassword}</h2>
                  <p className="text-xs text-muted-foreground mt-1">
                    {forgotStep === 1 && copy.resetIntro}
                    {forgotStep === 2 && copy.resetOtpIntro}
                    {forgotStep === 3 && copy.resetNewPasswordIntro}
                  </p>
                </div>

                {forgotStep === 1 && (
                  <>
                    <div>
                      <Label htmlFor="forgot-phone">{copy.phoneNumber}</Label>
                      <Input
                        id="forgot-phone"
                        placeholder={copy.phonePlaceholder}
                        value={forgotData.phone_number}
                        onChange={(e) => setForgotData((prev) => ({ ...prev, phone_number: e.target.value }))}
                      />
                    </div>
                    <Button
                      className="w-full"
                      onClick={handleForgotRequestOtp}
                      disabled={isLoading || forgotData.phone_number.trim().length < 9}
                    >
                      {isLoading ? copy.sending : copy.sendResetCode}
                    </Button>
                  </>
                )}

                {forgotStep === 2 && (
                  <>
                    <div>
                      <Label htmlFor="forgot-otp">{copy.otpCode}</Label>
                      <Input
                        id="forgot-otp"
                        placeholder={copy.otpPlaceholder}
                        value={forgotData.otp_code}
                        onChange={(e) => setForgotData((prev) => ({ ...prev, otp_code: e.target.value }))}
                      />
                    </div>
                    {forgotDebugOtp && (
                      <p className="text-xs text-muted">
                        {copy.debugOtp}: <span className="font-semibold">{forgotDebugOtp}</span>
                      </p>
                    )}
                    <div className="grid grid-cols-2 gap-2">
                      <Button variant="outline" onClick={handleForgotRequestOtp} disabled={isLoading}>
                        {copy.resend}
                      </Button>
                      <Button
                        onClick={handleForgotVerifyOtp}
                        disabled={isLoading || forgotData.otp_code.trim().length < 4}
                      >
                        {isLoading ? copy.verifying : copy.verify}
                      </Button>
                    </div>
                  </>
                )}

                {forgotStep === 3 && (
                  <>
                    <div>
                      <Label htmlFor="forgot-new-password">{copy.newPassword}</Label>
                      <PasswordInput
                        id="forgot-new-password"
                        placeholder={copy.passwordPlaceholder}
                        value={forgotData.new_password}
                        onChange={(e) => setForgotData((prev) => ({ ...prev, new_password: e.target.value }))}
                      />
                    </div>
                    <div>
                      <Label htmlFor="forgot-confirm-password">{copy.confirmNewPassword}</Label>
                      <PasswordInput
                        id="forgot-confirm-password"
                        placeholder={copy.confirmNewPasswordPlaceholder}
                        value={forgotData.confirm_password}
                        onChange={(e) => setForgotData((prev) => ({ ...prev, confirm_password: e.target.value }))}
                      />
                    </div>
                    {forgotData.new_password && forgotData.confirm_password && forgotData.new_password !== forgotData.confirm_password && (
                      <p className="text-xs text-red-600">{copy.passwordMismatch}</p>
                    )}
                    <Button
                      className="w-full"
                      onClick={handleResetPassword}
                      disabled={
                        isLoading ||
                        forgotData.new_password.length < 8 ||
                        forgotData.new_password !== forgotData.confirm_password
                      }
                    >
                      {isLoading ? copy.resetting : copy.resetPasswordButton}
                    </Button>
                  </>
                )}

                <button
                  type="button"
                  className="w-full text-center text-xs text-muted-foreground hover:text-foreground underline"
                  onClick={() => {
                    setForgotStep(1);
                    setForgotData({ phone_number: "", otp_code: "", reset_token: "", new_password: "", confirm_password: "" });
                    setForgotDebugOtp(null);
                    switchMode("signin");
                  }}
                >
                  {copy.backToSignIn}
                </button>
              </div>
            )}

            {error && (
              <div className="mt-4 rounded-[var(--radius)] border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                {error}
              </div>
            )}
            {success && (
              <div className="mt-4 rounded-[var(--radius)] border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-700">
                {success}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
