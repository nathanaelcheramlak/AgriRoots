import { api } from "./api";

export const accountApi = {
  requestPhoneChange: async ({ current_password, new_phone_number }) =>
    api.post("/api/auth/users/me/phone-change/request", {
      current_password,
      new_phone_number,
    }),

  confirmPhoneChange: async ({ current_password, new_phone_number, otp_code }) =>
    api.post("/api/auth/users/me/phone-change/confirm", {
      current_password,
      new_phone_number,
      otp_code,
    }),

  deleteAccount: async ({ current_password }) =>
    api.delete("/api/users/me", {
      data: { current_password },
    }),
};
