import { api } from "./api";

const CHAT_SEND_TIMEOUT_MS = 120000;

export const chatApi = {
  getSessions: async (limit = 20, offset = 0) => {
    return api.get("/api/chat/sessions", {
      params: { limit, offset },
    });
  },

  createSession: async (title) => {
    return api.post("/api/chat/sessions", { title });
  },

  renameSession: async (sessionId, title) => {
    return api.patch(`/api/chat/sessions/${sessionId}`, { title });
  },

  deleteSession: async (sessionId) => {
    return api.delete(`/api/chat/sessions/${sessionId}`);
  },

  getSessionMessages: async (sessionId, limit = 50, offset = 0) => {
    return api.get(`/api/chat/sessions/${sessionId}/messages`, {
      params: { limit, offset },
    });
  },

  sendMessage: async (sessionId, message, imageFile, audioFile, languageCode) => {
    const formData = new FormData();
    if (message) {
      formData.append("message", message);
    }
    if (languageCode) {
      formData.append("language_code", languageCode);
    }
    if (imageFile) {
      formData.append("image", imageFile);
    }
    if (audioFile) {
      const extension = audioFile.type.includes("wav")
        ? "wav"
        : audioFile.type.includes("ogg")
          ? "ogg"
          : "webm";
      formData.append("audio", audioFile, `voice-message.${extension}`);
    }

    return api.post(`/api/chat/sessions/${sessionId}/messages`, formData, {
      headers: {
        "Content-Type": "multipart/form-data",
      },
      timeout: CHAT_SEND_TIMEOUT_MS,
    });
  },
};