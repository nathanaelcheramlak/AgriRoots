import { api } from "./api";

export const voiceApi = {
  transcribe: async (audioFile, languageCode) => {
    const formData = new FormData();
    const extension = audioFile.type.includes("wav")
      ? "wav"
      : audioFile.type.includes("ogg")
        ? "ogg"
        : "webm";
    formData.append("audio", audioFile, `voice-message.${extension}`);
    if (languageCode) {
      formData.append("language_code", languageCode);
    }

    return api.post("/api/voice/transcribe", formData, {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    });
  },

  synthesize: async (text, languageCode) => {
    return api.post(
      "/api/voice/synthesize",
      { text, language_code: languageCode },
      {
        responseType: "blob",
      }
    );
  },
};

