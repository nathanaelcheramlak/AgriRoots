import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  AlertTriangle,
  ArrowLeft,
  Bell,
  CalendarDays,
  CheckCircle,
  CloudSun,
  Loader2,
  MapPin,
  RefreshCw,
  ShieldCheck,
  Trash2,
} from "lucide-react";
import { alertsApi } from "@/lib/alerts";
import { extractErrorMessage } from "@/lib/errors";
import { useAuth } from "@/contexts/AuthContext";
import { useLanguage } from "@/contexts/LanguageContext";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const COPY = {
  en: {
    chat: "Chat",
    refresh: "Refresh",
    brand: "Farm alerts",
    title: "Farm risks that need attention",
    subtitle: "Farmly checks your farm weather and crops, then turns risky conditions into simple actions.",
    unread: "unread",
    urgent: "Urgent",
    active: "Other active alerts",
    history: "History",
    noAlertsTitle: "No urgent farm risks right now.",
    noAlertsBody: "Refresh alerts before spraying, fertilizer application, harvest, or field work.",
    whatToDo: "What to do",
    markRead: "Mark as read",
    delete: "Delete",
    deleteConfirm: "Delete this alert?",
    alertDeleted: "Alert deleted.",
    generated: (count) =>
      count > 0 ? `${count} new farm alert${count === 1 ? "" : "s"} found.` : "Alerts refreshed. No new farm risks found.",
    loadError: "Could not load alerts.",
    generateError: "Could not refresh alerts.",
    updateError: "Could not update alert.",
    deleteError: "Could not delete alert.",
    riskDate: "Risk day",
    crops: "Crops",
    rain: "Rain",
    max: "Max",
    status: {
      active: "active",
      expired: "expired",
    },
    severity: {
      high: "high",
      medium: "medium",
      low: "low",
    },
  },
  am: {
    chat: "ውይይት",
    refresh: "አድስ",
    brand: "የእርሻ አስጠንቅቂያዎች",
    title: "ትኩረት የሚፈልጉ የእርሻ አደጋዎች",
    subtitle: "Farmly የእርሻዎን አየር ሁኔታ እና ሰብሎች ይፈትሻል፣ ከዚያም ቀላል የተግባር ምክር ይሰጣል።",
    unread: "ያልተነበበ",
    urgent: "አስቸኳይ",
    active: "ሌሎች ንቁ አስጠንቅቂያዎች",
    history: "ታሪክ",
    noAlertsTitle: "አሁን አስቸኳይ የእርሻ አደጋ የለም።",
    noAlertsBody: "ከመርጨት፣ ከማዳበሪያ፣ ከሰብል መሰብሰብ ወይም ከማሳ ስራ በፊት አስጠንቅቂያዎችን ያድሱ።",
    whatToDo: "ምን ማድረግ እንዳለብዎ",
    markRead: "እንደተነበበ ምልክት አድርግ",
    delete: "አጥፋ",
    deleteConfirm: "ይህን አስጠንቅቂያ ማጥፋት ይፈልጋሉ?",
    alertDeleted: "አስጠንቅቂያው ተጠፍቷል።",
    generated: (count) =>
      count > 0 ? `${count} አዲስ የእርሻ አስጠንቅቂያ ተገኝቷል።` : "አስጠንቅቂያዎች ታድሰዋል። አዲስ የእርሻ አደጋ አልተገኘም።",
    loadError: "አስጠንቅቂያዎችን መጫን አልተቻለም።",
    generateError: "አስጠንቅቂያዎችን ማደስ አልተቻለም።",
    updateError: "አስጠንቅቂያውን ማዘመን አልተቻለም።",
    deleteError: "አስጠንቅቂያውን ማጥፋት አልተቻለም።",
    riskDate: "የአደጋ ቀን",
    crops: "ሰብሎች",
    rain: "ዝናብ",
    max: "ከፍተኛ",
    status: {
      active: "ንቁ",
      expired: "ጊዜው ያለፈ",
    },
    severity: {
      high: "ከፍተኛ",
      medium: "መካከለኛ",
      low: "ዝቅተኛ",
    },
  },
};

const severityStyles = {
  high: {
    card: "border-red-200 bg-red-50",
    badge: "bg-red-600 text-white",
    icon: "text-red-600",
  },
  medium: {
    card: "border-amber-200 bg-amber-50",
    badge: "bg-amber-500 text-white",
    icon: "text-amber-700",
  },
  low: {
    card: "border-emerald-200 bg-emerald-50",
    badge: "bg-emerald-700 text-white",
    icon: "text-emerald-700",
  },
};

const severityRank = { high: 0, medium: 1, low: 2 };

function safeDate(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

function formatDateTime(value, language) {
  const date = safeDate(value);
  if (!date) return "";
  return new Intl.DateTimeFormat(language === "am" ? "am-ET" : "en", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function formatRiskDate(value, language) {
  const date = safeDate(value ? `${value}T00:00:00` : "");
  if (!date) return "";
  return new Intl.DateTimeFormat(language === "am" ? "am-ET" : "en", {
    month: "short",
    day: "numeric",
  }).format(date);
}

function sortAlerts(items) {
  return [...items].sort((a, b) => {
    const unreadDelta = Number(a.is_read) - Number(b.is_read);
    if (unreadDelta !== 0) return unreadDelta;
    const severityDelta = (severityRank[a.severity] ?? 9) - (severityRank[b.severity] ?? 9);
    if (severityDelta !== 0) return severityDelta;
    return String(a.risk_date || b.created_at || "").localeCompare(String(b.risk_date || a.created_at || ""));
  });
}

function groupAlerts(alerts) {
  const urgent = [];
  const active = [];
  const history = [];

  for (const alert of alerts) {
    const isActive = (alert.status || "active") === "active";
    const isUrgent = isActive && !alert.is_read && ["high", "medium"].includes(alert.severity);
    if (isUrgent) {
      urgent.push(alert);
    } else if (isActive) {
      active.push(alert);
    } else {
      history.push(alert);
    }
  }

  return [
    { key: "urgent", titleKey: "urgent", items: sortAlerts(urgent) },
    { key: "active", titleKey: "active", items: sortAlerts(active) },
    { key: "history", titleKey: "history", items: sortAlerts(history) },
  ].filter((group) => group.items.length > 0);
}

function AlertCard({ alert, onMarkRead, onDelete, copy, language }) {
  const styles = severityStyles[alert.severity] || severityStyles.low;
  const forecast = alert.raw_weather?.forecast_days?.slice(0, 5) || [];
  const crops = alert.recommendation_context?.crops || [];
  const isExpired = alert.status === "expired";

  return (
    <Card className={`${styles.card} overflow-hidden ${isExpired ? "opacity-75" : ""}`}>
      <CardHeader className="flex flex-row items-start justify-between gap-3 pb-3">
        <div className="flex min-w-0 items-start gap-3">
          <div className="mt-0.5 rounded-md bg-white/80 p-2 shadow-sm">
            {isExpired ? (
              <ShieldCheck className={`h-5 w-5 ${styles.icon}`} />
            ) : (
              <AlertTriangle className={`h-5 w-5 ${styles.icon}`} />
            )}
          </div>
          <div className="min-w-0">
            <CardTitle className="text-base leading-6 sm:text-lg">{alert.title}</CardTitle>
            <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
              {alert.risk_date && (
                <span className="inline-flex items-center gap-1">
                  <CalendarDays className="h-3.5 w-3.5" />
                  {copy.riskDate}: {formatRiskDate(alert.risk_date, language)}
                </span>
              )}
              {alert.location_used && (
                <span className="inline-flex items-center gap-1">
                  <MapPin className="h-3.5 w-3.5" />
                  {alert.location_used}
                </span>
              )}
              <span>{formatDateTime(alert.created_at, language)}</span>
            </div>
          </div>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-2">
          <span className={`rounded-full px-2.5 py-1 text-xs font-bold capitalize ${styles.badge}`}>
            {copy.severity[alert.severity] || alert.severity}
          </span>
          {alert.status && alert.status !== "active" && (
            <span className="rounded-full bg-white/80 px-2 py-0.5 text-[11px] font-semibold text-muted-foreground">
              {copy.status[alert.status] || alert.status}
            </span>
          )}
          {!alert.is_read && (
            <span className="rounded-full bg-white/80 px-2 py-0.5 text-[11px] font-semibold text-foreground">
              {copy.unread}
            </span>
          )}
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        <p className="text-sm leading-6 text-foreground">{alert.message}</p>

        {crops.length > 0 && (
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className="font-semibold text-muted-foreground">{copy.crops}</span>
            {crops.slice(0, 4).map((crop) => (
              <span key={crop} className="rounded-full border border-white/80 bg-white/75 px-2.5 py-1 font-medium text-foreground">
                {crop}
              </span>
            ))}
          </div>
        )}

        {alert.action_text && (
          <div className="rounded-md border border-white/70 bg-white/75 p-3 text-sm leading-6">
            <p className="font-semibold text-foreground">{copy.whatToDo}</p>
            <p className="mt-1 text-muted-foreground">{alert.action_text}</p>
          </div>
        )}

        {forecast.length > 0 && (
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
            {forecast.map((day) => (
              <div key={day.date} className="rounded-md border border-white/70 bg-white/70 p-2 text-xs">
                <p className="font-semibold text-foreground">{day.date}</p>
                <p className="mt-1 text-muted-foreground">{copy.rain}: {day.rain_mm ?? "-"} mm</p>
                <p className="text-muted-foreground">{copy.max}: {day.temp_max_c ?? "-"} C</p>
              </div>
            ))}
          </div>
        )}

        <div className="flex flex-wrap gap-2">
          {!alert.is_read && (
            <Button variant="outline" size="sm" onClick={() => onMarkRead(alert.alert_id)} className="gap-2 bg-white/80">
              <CheckCircle className="h-4 w-4" />
              {copy.markRead}
            </Button>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={() => onDelete(alert.alert_id)}
            className="gap-2 border-red-200 bg-white/80 text-red-700 hover:bg-red-50"
          >
            <Trash2 className="h-4 w-4" />
            {copy.delete}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

export default function AlertsPage() {
  const navigate = useNavigate();
  const { accessToken, isHydrated } = useAuth();
  const { language } = useLanguage();
  const copy = COPY[language] || COPY.en;
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    if (!isHydrated) return;
    if (!accessToken) {
      navigate("/auth-options", { replace: true });
      return;
    }
    loadAlerts();
  }, [accessToken, isHydrated, navigate]);

  const unreadCount = useMemo(() => alerts.filter((alert) => !alert.is_read).length, [alerts]);
  const groupedAlerts = useMemo(() => groupAlerts(alerts), [alerts]);

  async function loadAlerts({ silent = false } = {}) {
    if (!silent) setLoading(true);
    setError("");
    try {
      const { data } = await alertsApi.listAlerts(100, 0);
      setAlerts(data);
    } catch (err) {
      setError(extractErrorMessage(err, copy.loadError));
    } finally {
      if (!silent) setLoading(false);
    }
  }

  async function handleGenerateWeatherAlerts() {
    setGenerating(true);
    setError("");
    setSuccess("");
    try {
      const { data } = await alertsApi.generateWeatherAlerts(language);
      setSuccess(copy.generated(data.generated_count));
      await loadAlerts({ silent: true });
    } catch (err) {
      setError(extractErrorMessage(err, copy.generateError));
    } finally {
      setGenerating(false);
    }
  }

  async function handleMarkRead(alertId) {
    try {
      const { data } = await alertsApi.markRead(alertId);
      setAlerts((previous) =>
        previous.map((alert) => (alert.alert_id === alertId ? data.alert : alert))
      );
    } catch (err) {
      setError(extractErrorMessage(err, copy.updateError));
    }
  }

  async function handleDeleteAlert(alertId) {
    if (!confirm(copy.deleteConfirm)) return;
    setError("");
    setSuccess("");
    try {
      await alertsApi.deleteAlert(alertId);
      setAlerts((previous) => previous.filter((alert) => alert.alert_id !== alertId));
      setSuccess(copy.alertDeleted);
    } catch (err) {
      setError(extractErrorMessage(err, copy.deleteError));
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
    <main className="min-h-screen bg-[linear-gradient(180deg,#f0fdf4_0%,var(--background)_34%)]">
      <header className="border-b border-border bg-card/95 backdrop-blur">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-6">
          <Link to="/main-page" className="inline-flex min-h-10 items-center gap-2 text-sm font-medium text-muted-foreground hover:text-foreground">
            <ArrowLeft className="h-4 w-4" />
            {copy.chat}
          </Link>
          <Button onClick={handleGenerateWeatherAlerts} disabled={generating} className="gap-2 whitespace-nowrap">
            {generating ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            {copy.refresh}
          </Button>
        </div>
      </header>

      <section className="mx-auto max-w-5xl px-4 py-6 sm:px-6">
        <div className="mb-5 rounded-md border border-green-100 bg-white/90 p-5 shadow-sm sm:p-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="flex items-center gap-2 text-primary">
                <Bell className="h-5 w-5" />
                <span className="text-sm font-bold uppercase tracking-wide">{copy.brand}</span>
              </div>
              <h1 className="mt-3 text-2xl font-extrabold text-foreground sm:text-3xl">
                {copy.title}
              </h1>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
                {copy.subtitle}
              </p>
            </div>
            <div className="rounded-md border border-green-100 bg-green-50 px-4 py-3 text-sm text-green-900">
              <p className="font-bold">{unreadCount} {copy.unread}</p>
              <p className="text-xs">{groupedAlerts.length} {copy.brand.toLowerCase()}</p>
            </div>
          </div>
        </div>

        {error && (
          <div className="mb-4 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}
        {success && (
          <div className="mb-4 rounded-md border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">
            {success}
          </div>
        )}

        {alerts.length === 0 ? (
          <div className="grid place-items-center rounded-md border border-dashed border-green-200 bg-white/80 px-6 py-16 text-center">
            <CloudSun className="h-10 w-10 text-primary" />
            <h2 className="mt-4 text-xl font-bold">{copy.noAlertsTitle}</h2>
            <p className="mt-2 max-w-md text-sm leading-6 text-muted-foreground">
              {copy.noAlertsBody}
            </p>
            <Button onClick={handleGenerateWeatherAlerts} disabled={generating} className="mt-5 gap-2">
              {generating ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
              {copy.refresh}
            </Button>
          </div>
        ) : (
          <div className="grid gap-6">
            {groupedAlerts.map((group) => (
              <section key={group.key} className="grid gap-3">
                <h2 className="text-sm font-bold uppercase tracking-wide text-muted-foreground">
                  {copy[group.titleKey]}
                </h2>
                <div className="grid gap-4">
                  {group.items.map((alert) => (
                    <AlertCard
                      key={alert.alert_id}
                      alert={alert}
                      onMarkRead={handleMarkRead}
                      onDelete={handleDeleteAlert}
                      copy={copy}
                      language={language}
                    />
                  ))}
                </div>
              </section>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
