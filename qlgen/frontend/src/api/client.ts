import axios from 'axios';
import { getAccessToken } from '../context/AuthContext';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

const client = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true,
});

// Request interceptor: attach Bearer token
client.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor: auto-refresh on 401
let isRefreshing = false;
let failedQueue: { resolve: (token: string) => void; reject: (err: unknown) => void }[] = [];

function processQueue(error: unknown, token: string | null) {
  failedQueue.forEach((p) => {
    if (error) {
      p.reject(error);
    } else {
      p.resolve(token!);
    }
  });
  failedQueue = [];
}

client.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // Don't retry auth endpoints or already retried requests
    if (
      error.response?.status !== 401 ||
      originalRequest._retry ||
      originalRequest.url?.includes('/auth/')
    ) {
      return Promise.reject(error);
    }

    if (isRefreshing) {
      return new Promise((resolve, reject) => {
        failedQueue.push({
          resolve: (token: string) => {
            originalRequest.headers.Authorization = `Bearer ${token}`;
            resolve(client(originalRequest));
          },
          reject,
        });
      });
    }

    originalRequest._retry = true;
    isRefreshing = true;

    try {
      const resp = await axios.post(`${API_BASE}/auth/refresh`, {}, { withCredentials: true });
      const newToken = resp.data.access_token;

      // Update the module-level token via dynamic import to avoid circular deps
      // The AuthContext's login will be called by the component that catches this
      // For now, update headers directly
      processQueue(null, newToken);

      originalRequest.headers.Authorization = `Bearer ${newToken}`;
      return client(originalRequest);
    } catch (refreshError) {
      processQueue(refreshError, null);
      // Redirect to login — will be handled by AuthContext
      window.location.href = '/welcome';
      return Promise.reject(refreshError);
    } finally {
      isRefreshing = false;
    }
  },
);

export default client;
export { API_BASE };
