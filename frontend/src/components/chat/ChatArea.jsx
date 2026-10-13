import { useEffect, useRef } from "react";
import { Link } from "react-router-dom";
import { MessageBubble } from "./MessageBubble";
import { ChatInput } from "./ChatInput";
import { AlertTriangle, ChevronRight, Menu, Sprout, CloudRain, Bug, Leaf, Globe } from "lucide-react";
import { Button } from "@/components/ui/button";
import { SUPPORTED_LANGUAGES } from "@/contexts/LanguageContext";

const COPY = {
  en: {
    title: "Farmly Assistant",
    responseLanguage: "Response language",
    alertBannerTitle: "Farm alerts need attention",
    alertBannerMore: "View",
    welcomeTitle: "Welcome to Farmly",
    welcomeSubtitle: "Your personal agricultural assistant. Ask me anything or choose an option below.",
    quickActions: [
      { icon: Sprout, label: "Recommend a crop", text: "Can you recommend a crop suitable for my location?" },
      { icon: CloudRain, label: "Check the weather", text: "What is the weather forecast for the next few days?" },
      { icon: Bug, label: "Diagnose my plant", text: "I need help diagnosing a problem with my plant. Should I upload a photo?" },
      { icon: Leaf, label: "Fertilizer advice", text: "What fertilizer should I use for my farm?" },
    ],
  },
  am: {
    title: "Farmly ረዳት",
    responseLanguage: "የመልስ ቋንቋ",
    alertBannerTitle: "የእርሻ አስጠንቅቂያ ትኩረት ይፈልጋል",
    alertBannerMore: "ይመልከቱ",
    welcomeTitle: "ወደ Farmly እንኳን በደህና መጡ",
    welcomeSubtitle: "የግብርና ጥያቄዎን በጽሑፍ፣ በድምጽ ወይም በምስል ይጠይቁ።",
    quickActions: [
      { icon: Sprout, label: "የሰብል ምክር", text: "ለአካባቢዬ የሚስማማ ሰብል ምን ልዝራ?" },
      { icon: CloudRain, label: "የአየር ሁኔታ", text: "የቀጣዮቹ ቀናት የአየር ሁኔታ ትንበያ ምን ይመስላል?" },
      { icon: Bug, label: "ተክል መመርመር", text: "በተክሌ ላይ ችግር አለ። ፎቶ ልላክ?" },
      { icon: Leaf, label: "የማዳበሪያ ምክር", text: "ለእርሻዬ ምን አይነት ማዳበሪያ ልጠቀም?" },
    ],
  },
};

export function ChatArea({ 
  messages, 
  urgentAlerts = [],
  onSendMessage, 
  isLoading, 
  onOpenSidebar,
  onSpeakMessage,
  speakingMessageId,
  language = "en",
  setLanguage
}) {
  const bottomRef = useRef(null);
  const copy = COPY[language] || COPY.en;

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  return (
    <div className="flex flex-1 flex-col h-[100dvh] bg-background">
      {/* Header */}
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-border bg-card px-4 shadow-sm relative z-10">
        <div className="flex items-center gap-2">
          <Button 
            variant="ghost" 
            size="icon" 
            className="md:hidden -ml-2"
            onClick={onOpenSidebar}
          >
            <Menu className="h-5 w-5" />
          </Button>
          <h1 className="text-lg font-semibold text-foreground">{copy.title}</h1>
        </div>
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <div className="flex items-center gap-1 rounded-md border border-border bg-background px-2 py-1">
            <Globe className="h-4 w-4" />
            <select
              value={language}
              onChange={(event) => setLanguage?.(event.target.value)}
              className="bg-transparent text-xs font-medium text-foreground outline-none"
              aria-label={copy.responseLanguage}
            >
              {SUPPORTED_LANGUAGES.map((item) => (
                <option key={item.code} value={item.code}>
                  {item.tag}
                </option>
              ))}
            </select>
          </div>
        </div>
      </header>

      {urgentAlerts.length > 0 && (
        <Link
          to="/alerts"
          className="mx-3 mt-3 flex shrink-0 items-start gap-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-3 text-sm text-amber-950 shadow-sm transition-colors hover:bg-amber-100 md:mx-6"
        >
          <div className="mt-0.5 rounded-md bg-white/80 p-1.5 text-amber-700">
            <AlertTriangle className="h-4 w-4" />
          </div>
          <div className="min-w-0 flex-1">
            <p className="font-semibold leading-5">{copy.alertBannerTitle}</p>
            <p className="mt-0.5 truncate text-xs text-amber-900/80">
              {urgentAlerts[0]?.title}
              {urgentAlerts.length > 1 ? ` +${urgentAlerts.length - 1}` : ""}
            </p>
          </div>
          <span className="flex shrink-0 items-center gap-1 text-xs font-semibold">
            {copy.alertBannerMore}
            <ChevronRight className="h-4 w-4" />
          </span>
        </Link>
      )}

      {/* Messages / Empty State */}
      <div className="flex-1 overflow-y-auto p-4 md:p-6 custom-scrollbar">
        {messages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center max-w-2xl mx-auto">
            <div className="mb-8 flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10 text-primary">
              <Leaf className="h-8 w-8" />
            </div>
            <h2 className="mb-2 text-2xl font-bold text-center">{copy.welcomeTitle}</h2>
            <p className="mb-8 text-center text-muted-foreground">
              {copy.welcomeSubtitle}
            </p>
            
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full">
              {copy.quickActions.map((action, idx) => (
                <button
                  key={idx}
                  onClick={() => onSendMessage(action.text, null)}
                  className="flex items-center gap-3 rounded-xl border border-border bg-card p-4 text-left transition-all hover:bg-muted hover:shadow-sm"
                >
                  <div className="rounded-full bg-primary/10 p-2 text-primary">
                    <action.icon className="h-5 w-5" />
                  </div>
                  <span className="font-medium text-sm">{action.label}</span>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="mx-auto max-w-3xl">
            {messages.map((msg) => (
              <MessageBubble
                key={msg.message_id}
                message={msg}
                onSpeak={onSpeakMessage}
                isSpeaking={speakingMessageId === msg.message_id}
              />
            ))}
            {isLoading && (
              <div className="flex items-center gap-2 text-muted-foreground p-4">
                <div className="h-2 w-2 animate-bounce rounded-full bg-primary/50" />
                <div className="h-2 w-2 animate-bounce rounded-full bg-primary/50 delay-75" />
                <div className="h-2 w-2 animate-bounce rounded-full bg-primary/50 delay-150" />
              </div>
            )}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* Input */}
      <ChatInput onSend={onSendMessage} disabled={isLoading} language={language} />
    </div>
  );
}
