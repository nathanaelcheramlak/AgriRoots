import axios from "axios";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ||
  import.meta.env.NEXT_PUBLIC_API_BASE_URL ||
  "http://127.0.0.1:8000";

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 100000,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("farmly_access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export { api, API_BASE_URL };
