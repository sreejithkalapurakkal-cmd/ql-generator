import React, { useEffect, useRef, useState, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Spin, Typography, message } from 'antd';
import { googleCallback } from '../api/authApi';
import { useAuth } from '../context/AuthContext';

const { Text } = Typography;

const AuthCallbackPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { login } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const processed = useRef(false);

  const handleCallback = useCallback(async () => {
    const code = searchParams.get('code');
    const errorParam = searchParams.get('error');

    if (errorParam) {
      setError(`Google authentication failed: ${errorParam}`);
      setTimeout(() => navigate('/login'), 3000);
      return;
    }

    if (!code) {
      setError('No authorization code received');
      setTimeout(() => navigate('/login'), 3000);
      return;
    }

    try {
      const redirectUri = `${window.location.origin}/auth/callback`;
      const resp = await googleCallback(code, redirectUri);
      const { access_token, user } = resp.data;
      login(access_token, user);
      navigate('/dashboard', { replace: true });
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        'Authentication failed';
      setError(detail);
      message.error(detail);
      setTimeout(() => navigate('/login'), 3000);
    }
  }, [searchParams, navigate, login]);

  useEffect(() => {
    if (processed.current) return;
    processed.current = true;
    handleCallback(); // eslint-disable-line react-hooks/set-state-in-effect
  }, [handleCallback]);

  if (error) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ textAlign: 'center' }}>
          <Text type="danger" style={{ fontSize: 16 }}>{error}</Text>
          <br />
          <Text type="secondary" style={{ marginTop: 8 }}>Redirecting to login...</Text>
        </div>
      </div>
    );
  }

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ textAlign: 'center' }}>
        <Spin size="large" />
        <div style={{ marginTop: 16 }}>
          <Text type="secondary">Signing you in...</Text>
        </div>
      </div>
    </div>
  );
};

export default AuthCallbackPage;
