import { api } from "./api";

export const profileApi = {
  getMe: async () => api.get("/api/auth/me"),
  getProfile: async () => api.get("/api/users/me/profile"),
  updateProfile: async (payload) => api.patch("/api/users/me/profile", payload),
};
