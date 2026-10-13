import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { getVoiceLanguageCode, useLanguage } from "@/contexts/LanguageContext";
import { api } from "@/lib/api";
import { alertsApi } from "@/lib/alerts";
import { chatApi } from "@/lib/chat";
import { voiceApi } from "@/lib/voice";
import { ChatSidebar } from "@/components/chat/ChatSidebar";
import { ChatArea } from "@/components/chat/ChatArea";

const COPY = {
  en: {
    voiceMessage: "Voice message",
    imageDiagnosis: "Image Diagnosis",
    transcribingVoice: "Transcribing voice...",
    noTranscript: "Voice transcription returned no text.",
    transcriptionFailed: "Voice transcription failed. Please try again.",
    imageDiagnosisFailed: "Image diagnosis failed. Please try again with a clear plant photo.",
    sendFailed: "Message failed. Please try again.",
  },
  am: {
    voiceMessage: "የድምጽ መልዕክት",
    imageDiagnosis: "የምስል ምርመራ",
    transcribingVoice: "ድምጽ በጽሑፍ በመቀየር ላይ...",
    noTranscript: "የድምጽ መልዕክት ወደ ጽሑፍ አልተቀየረም።",
    transcriptionFailed: "የድምጽ መልዕክት ወደ ጽሑፍ መቀየር አልተሳካም። እባክዎ እንደገና ይሞክሩ።",
    imageDiagnosisFailed: "የምስል ምርመራ አልተሳካም። እባክዎ ግልጽ የተክል ፎቶ በመጠቀም እንደገና ይሞክሩ።",
    sendFailed: "መልዕክቱ አልተላከም። እባክዎ እንደገና ይሞክሩ።",
  },
};

export default function MainPage() {
  const navigate = useNavigate();
  const { accessToken, clearToken, isHydrated } = useAuth();
  const { language, setLanguage } = useLanguage();
  const copy = COPY[language] || COPY.en;

  const [checkingOnboarding, setCheckingOnboarding] = useState(true);
  const [sessions, setSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [urgentAlerts, setUrgentAlerts] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [speakingMessageId, setSpeakingMessageId] = useState(null);
  const audioElementRef = useRef(null);
  const audioUrlRef = useRef(null);
  const audioRequestIdRef = useRef(0);
  const imagePreviewUrlsRef = useRef(new Set());

  useEffect(() => {
    return () => {
      audioElementRef.current?.pause();
      if (audioUrlRef.current) {
        URL.revokeObjectURL(audioUrlRef.current);
      }
      imagePreviewUrlsRef.current.forEach((url) => URL.revokeObjectURL(url));
      imagePreviewUrlsRef.current.clear();
    };
  }, []);

  useEffect(() => {
    if (!isHydrated) return;
    if (!accessToken) {
      navigate("/auth-options", { replace: true });
      return;
    }

    api
      .get("/api/auth/me")
      .then(({ data }) => {
        if (!data?.onboarding_completed) {
          navigate("/onboarding/location", { replace: true });
          return;
        }
        setCheckingOnboarding(false);
      })
      .catch(() => {
        clearToken();
        navigate("/auth-options", { replace: true });
      });
  }, [accessToken, clearToken, isHydrated, navigate]);

  useEffect(() => {
    if (checkingOnboarding) return;
    fetchSessions();
    fetchUrgentAlerts();
  }, [checkingOnboarding]);

  const fetchSessions = async ({ syncMessages = true } = {}) => {
    try {
      const { data } = await chatApi.getSessions();
      setSessions(data);

      if (!syncMessages) {
        return;
      }

      const saved = localStorage.getItem("farmly_active_session_id");
      const savedExists = saved && data.some((s) => s.session_id === saved);

      if (savedExists) {
        handleSelectSession(saved);
      } else if (data.length > 0) {
        handleSelectSession(data[0].session_id);
      } else {
        setActiveSessionId(null);
        setMessages([]);
      }
    } catch (err) {
      console.error("Failed to fetch sessions", err);
    }
  };

  const fetchUrgentAlerts = async () => {
    try {
      const { data } = await alertsApi.listAlerts(20, 0);
      const severityRank = { high: 0, medium: 1, low: 2 };
      const alerts = data
        .filter((alert) => {
          const isActive = (alert.status || "active") === "active";
          return isActive && !alert.is_read && ["high", "medium"].includes(alert.severity);
        })
        .sort((a, b) => (severityRank[a.severity] ?? 9) - (severityRank[b.severity] ?? 9))
        .slice(0, 2);
      setUrgentAlerts(alerts);
    } catch (err) {
      console.error("Failed to fetch urgent alerts", err);
    }
  };

  const handleSelectSession = async (sessionId) => {
    setActiveSessionId(sessionId);
    localStorage.setItem("farmly_active_session_id", sessionId);

    try {
      const { data } = await chatApi.getSessionMessages(sessionId);
      setMessages(data);
    } catch (err) {
      console.error("Failed to fetch messages", err);
    }
  };

  const handleNewSession = () => {
    setActiveSessionId(null);
    localStorage.removeItem("farmly_active_session_id");
    setMessages([]);
  };

  const handleRenameSession = async (sessionId, title) => {
    try {
      const { data } = await chatApi.renameSession(sessionId, title);
      setSessions((prev) => prev.map((s) => (s.session_id === sessionId ? data : s)));
    } catch (err) {
      console.error("Failed to rename session", err);
    }
  };

  const handleDeleteSession = async (sessionId) => {
    try {
      await chatApi.deleteSession(sessionId);
      const next = sessions.filter((s) => s.session_id !== sessionId);
      setSessions(next);

      if (activeSessionId === sessionId) {
        if (next.length > 0) {
          handleSelectSession(next[0].session_id);
        } else {
          handleNewSession();
        }
      }
    } catch (err) {
      console.error("Failed to delete session", err);
    }
  };

  const autoTitleFromFirstMessage = useMemo(
    () => async (sessionId, text) => {
      const trimmed = text.trim();
      if (!trimmed) return;
      const shortTitle = trimmed.length > 40 ? `${trimmed.slice(0, 40)}...` : trimmed;
      await handleRenameSession(sessionId, shortTitle);
    },
    []
  );

  const stopAssistantAudio = () => {
    audioRequestIdRef.current += 1;
    audioElementRef.current?.pause();
    if (audioUrlRef.current) {
      URL.revokeObjectURL(audioUrlRef.current);
      audioUrlRef.current = null;
    }
    audioElementRef.current = null;
    setSpeakingMessageId(null);
  };

  const playAssistantAudio = async (message) => {
    if (!message?.content) return;

    if (speakingMessageId === message.message_id) {
      stopAssistantAudio();
      return;
    }

    stopAssistantAudio();
    const requestId = audioRequestIdRef.current;
    const voiceLanguageCode = getVoiceLanguageCode(language);

    setSpeakingMessageId(message.message_id);
    try {
      const { data } = await voiceApi.synthesize(message.content, voiceLanguageCode);
      if (audioRequestIdRef.current !== requestId) {
        return;
      }
      const audioUrl = URL.createObjectURL(data);
      const audio = new Audio(audioUrl);

      audioUrlRef.current = audioUrl;
      audioElementRef.current = audio;

      const resetAudioState = () => {
        if (audioUrlRef.current === audioUrl) {
          URL.revokeObjectURL(audioUrl);
          audioUrlRef.current = null;
        }
        if (audioElementRef.current === audio) {
          audioElementRef.current = null;
        }
        setSpeakingMessageId(null);
      };

      audio.onended = resetAudioState;
      audio.onerror = resetAudioState;
      await audio.play();
    } catch (err) {
      console.error("Failed to play assistant audio", err);
      stopAssistantAudio();
    }
  };

  const createImagePreviewUrl = (imageFile) => {
    if (!imageFile) return "";
    const url = URL.createObjectURL(imageFile);
    imagePreviewUrlsRef.current.add(url);
    return url;
  };

  const addTempUserMessage = (sessionId, content, extra = {}) => {
    const trimmed = content?.trim() || "";
    if (!trimmed && !extra.image_preview_url) return null;
    const messageId = `temp-${Date.now()}`;

    setMessages((prev) => [
      ...prev,
      {
        message_id: messageId,
        session_id: sessionId,
        sender: "user",
        content: trimmed,
        sequence_no: prev.length + 1,
        created_at: new Date().toISOString(),
        ...extra,
      },
    ]);
    return messageId;
  };

  const updateTempUserMessage = (messageId, content) => {
    if (!messageId || !content?.trim()) return;
    setMessages((prev) =>
      prev.map((message) =>
        message.message_id === messageId ? { ...message, content: content.trim() } : message
      )
    );
  };

  const handleSendMessage = async (text, image, audio) => {
    let tempMessageId = null;
    const imagePreviewUrl = createImagePreviewUrl(image);
    try {
      setIsLoading(true);
      let outgoingText = text?.trim() || "";
      const voiceLanguageCode = getVoiceLanguageCode(language);

      let sessionId = activeSessionId;
      let wasNewSession = false;
      if (!sessionId) {
        const titleSnippet = outgoingText
          ? outgoingText.slice(0, 30)
          : audio
            ? copy.voiceMessage
            : copy.imageDiagnosis;
        const res = await chatApi.createSession(titleSnippet);
        sessionId = res.data.session_id;
        wasNewSession = true;
        setActiveSessionId(sessionId);
        localStorage.setItem("farmly_active_session_id", sessionId);
        setSessions((prev) => [res.data, ...prev]);
      }

      if (audio) {
        tempMessageId = addTempUserMessage(
          sessionId,
          copy.transcribingVoice,
          imagePreviewUrl ? { image_preview_url: imagePreviewUrl } : {}
        );
        const { data } = await voiceApi.transcribe(audio, voiceLanguageCode);
        outgoingText = data?.transcript?.trim() || "";
        if (!outgoingText) {
          throw new Error(copy.noTranscript);
        }
        updateTempUserMessage(tempMessageId, outgoingText);
      } else if (image) {
        tempMessageId = addTempUserMessage(
          sessionId,
          outgoingText || "[image uploaded for diagnosis]",
          { image_preview_url: imagePreviewUrl }
        );
      } else if (outgoingText && !image) {
        tempMessageId = addTempUserMessage(sessionId, outgoingText);
      }

      const res = await chatApi.sendMessage(sessionId, outgoingText, image, null, voiceLanguageCode);
      const { user_message, assistant_message } = res.data;
      const userMessage = imagePreviewUrl
        ? { ...user_message, image_preview_url: imagePreviewUrl }
        : user_message;

      setMessages((prev) => {
        const filtered = prev.filter((m) => !String(m.message_id).startsWith("temp-"));
        return [...filtered, userMessage, assistant_message];
      });

      const refreshSessionList = async () => {
        if (wasNewSession && userMessage?.content) {
          await autoTitleFromFirstMessage(sessionId, userMessage.content);
        }
        await fetchSessions({ syncMessages: false });
      };
      refreshSessionList().catch((err) => {
        console.error("Failed to refresh sessions after message", err);
      });

      if (audio && assistant_message?.content) {
        window.setTimeout(() => {
          playAssistantAudio(assistant_message);
        }, 0);
      }
    } catch (err) {
      console.error("Failed to send message", err);
      if (tempMessageId) {
        const failureMessage = audio
          ? copy.transcriptionFailed
          : image
            ? copy.imageDiagnosisFailed
            : copy.sendFailed;
        updateTempUserMessage(
          tempMessageId,
          failureMessage
        );
      }
    } finally {
      setIsLoading(false);
    }
  };

  if (!isHydrated || checkingOnboarding) return null;

  return (
    <div className="flex h-[100dvh] w-full overflow-hidden bg-background">
      <ChatSidebar
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelectSession={handleSelectSession}
        onNewSession={handleNewSession}
        onRenameSession={handleRenameSession}
        onDeleteSession={handleDeleteSession}
        isOpen={isSidebarOpen}
        setIsOpen={setIsSidebarOpen}
      />
      <ChatArea
        messages={messages}
        urgentAlerts={urgentAlerts}
        onSendMessage={handleSendMessage}
        isLoading={isLoading}
        onOpenSidebar={() => setIsSidebarOpen(true)}
        onSpeakMessage={playAssistantAudio}
        speakingMessageId={speakingMessageId}
        language={language}
        setLanguage={setLanguage}
      />
    </div>
  );
}
