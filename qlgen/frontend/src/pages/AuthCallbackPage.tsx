import React, { useEffect, useRef, useState, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Spin, Typography } from 'antd';
import { CloseCircleFilled } from '@ant-design/icons';
import { googleCallback } from '../api/authApi';
import { useAuth } from '../context/AuthContext';

const { Text } = Typography;

const AuthCallbackPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { login } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [countdown, setCountdown] = useState(4);
  const processed = useRef(false);

  const handleCallback = useCallback(async () => {
    const code = searchParams.get('code');
    const errorParam = searchParams.get('error');

    if (errorParam) {
      setError(
        errorParam === 'access_denied'
          ? 'Sign-in was cancelled. Please try again.'
          : `Sign-in failed: ${errorParam}`
      );
      return;
    }

    if (!code) {
      setError('No authorisation code was received. Please try signing in again.');
      return;
    }

    try {
      const redirectUri = `${window.location.origin}/auth/callback`;
      const resp = await googleCallback(code, redirectUri);
      const { access_token, user } = resp.data;
      login(access_token, user);
      navigate('/home', { replace: true });
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        'Authentication failed. Please try again.';
      setError(detail);
    }
  }, [searchParams, navigate, login]);

  useEffect(() => {
    if (processed.current) return;
    processed.current = true;
    handleCallback(); // eslint-disable-line react-hooks/set-state-in-effect
  }, [handleCallback]);

  // Countdown + redirect when error is set
  useEffect(() => {
    if (!error) return;
    const interval = setInterval(() => {
      setCountdown(c => {
        if (c <= 1) {
          clearInterval(interval);
          navigate('/welcome');
        }
        return c - 1;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [error, navigate]);

  if (error) {
    return (
      <div style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'var(--g50)',
      }}>
        <div style={{
          background: '#fff',
          border: '1px solid var(--g200)',
          borderRadius: 'var(--radius)',
          boxShadow: 'var(--shadow-md)',
          padding: '40px 48px',
          textAlign: 'center',
          maxWidth: 420,
          width: '100%',
        }}>
          <CloseCircleFilled style={{ fontSize: 40, color: 'var(--red)', marginBottom: 16 }} />
          <div style={{ fontWeight: 700, fontSize: 18, color: 'var(--g900)', marginBottom: 10 }}>
            Sign-in failed
          </div>
          <div style={{
            fontSize: 14,
            color: 'var(--g600)',
            lineHeight: 1.6,
            marginBottom: 24,
            padding: '10px 14px',
            background: '#fff5f5',
            border: '1px solid #fecaca',
            borderRadius: 'var(--radius-sm)',
          }}>
            {error}
          </div>
          <Text type="secondary" style={{ fontSize: 13 }}>
            Redirecting to sign-in in {countdown}s…
          </Text>
        </div>
      </div>
    );
  }

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'var(--g50)',
    }}>
      <div style={{ textAlign: 'center' }}>
        <Spin size="large" />
        <div style={{ marginTop: 16 }}>
          <Text type="secondary" style={{ fontSize: 14 }}>Signing you in…</Text>
        </div>
      </div>
    </div>
  );
};

export default AuthCallbackPage;
