import { api } from "./api";

export const alertsApi = {
  listAlerts: async (limit = 20, offset = 0) =>
    api.get("/api/alerts", {
      params: { limit, offset },
    }),

  generateWeatherAlerts: async (languageCode) =>
    api.post("/api/alerts/weather/generate", null, {
      params: languageCode ? { language_code: languageCode } : {},
    }),

  markRead: async (alertId) => api.patch(`/api/alerts/${alertId}/read`),

  deleteAlert: async (alertId) => api.delete(`/api/alerts/${alertId}`),
};
