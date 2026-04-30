import client from './client';

export interface AuthUser {
  id: string;
  email: string;
  name: string | null;
  picture_url: string | null;
  role: string;
  is_active: boolean;
  daily_credit_limit: number | null;
  created_at: string | null;
  last_login_at: string | null;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: AuthUser;
}

export const googleCallback = (code: string, redirectUri: string) =>
  client.post<TokenResponse>('/auth/google/callback', { code, redirect_uri: redirectUri });

export const refreshToken = () =>
  client.post<TokenResponse>('/auth/refresh');

export const logout = () =>
  client.post('/auth/logout');

export const getMe = () =>
  client.get<AuthUser>('/auth/me');
