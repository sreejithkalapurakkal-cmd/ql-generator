import { useState, useEffect } from 'react';
import { Tabs, Switch, Select, InputNumber, message, Spin } from 'antd';
import { useAuth } from '../context/AuthContext';
import { getSettings, updateSettings, UserSettings } from '../api/settingsApi';
import { SIGNAL_ALERT_THRESHOLD_OPTIONS as THRESHOLD_OPTIONS } from '../types';

const TONE_OPTIONS = [
  { value: 'direct', label: 'Direct' },
  { value: 'consultative', label: 'Consultative' },
  { value: 'formal', label: 'Formal' },
  { value: 'casual', label: 'Casual' },
];

const VOICE_OPTIONS = [
  { value: 'concise', label: 'Concise' },
  { value: 'consultative', label: 'Consultative' },
  { value: 'formal', label: 'Formal' },
];

const FORMAT_OPTIONS = [
  { value: 'email', label: 'Email' },
  { value: 'linkedin', label: 'LinkedIn' },
];

const VERBOSITY_OPTIONS = [
  { value: 'summary', label: 'Summary' },
  { value: 'detailed', label: 'Detailed' },
  { value: 'technical', label: 'Technical' },
];

export default function SettingsPage() {
  const { user: authUser } = useAuth();
  const [settings, setSettings] = useState<UserSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      const data = await getSettings();
      setSettings(data.settings);
    } catch {
      message.error('Failed to load settings');
    } finally {
      setLoading(false);
    }
  };

  const handleUpdate = async (section: string, key: string, value: unknown) => {
    if (!settings) return;
    setSaving(true);
    try {
      const update = { [section]: { [key]: value } };
      const data = await updateSettings(update as Partial<UserSettings>);
      setSettings(data.settings);
      message.success('Settings saved');
    } catch {
      message.error('Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Spin size="large" />
      </div>
    );
  }

  if (!settings) return null;

  const SettingRow = ({ label, description, children }: { label: string; description?: string; children: React.ReactNode }) => (
    <div className="flex items-center justify-between py-3 border-b border-gray-100 last:border-0">
      <div>
        <div className="text-sm font-medium text-gray-800">{label}</div>
        {description && <div className="text-xs text-gray-500 mt-0.5">{description}</div>}
      </div>
      <div>{children}</div>
    </div>
  );

  const items = [
    {
      key: 'profile',
      label: 'Profile',
      children: (
        <div className="max-w-xl">
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <div className="flex items-center gap-4 mb-6">
              {authUser?.picture_url ? (
                <img src={authUser.picture_url} alt="" className="w-12 h-12 rounded-full" />
              ) : (
                <div className="w-12 h-12 rounded-full bg-purple-100 flex items-center justify-center text-purple-700 font-semibold text-lg">
                  {authUser?.name?.[0] || '?'}
                </div>
              )}
              <div>
                <div className="font-semibold text-gray-900">{authUser?.name || 'User'}</div>
                <div className="text-sm text-gray-500">{authUser?.email}</div>
              </div>
            </div>
            <div className="text-xs text-gray-400">
              Role: {authUser?.role || 'user'} &middot; Member since {authUser?.created_at ? new Date(authUser.created_at).toLocaleDateString() : 'N/A'}
            </div>
          </div>
        </div>
      ),
    },
    {
      key: 'notifications',
      label: 'Notifications',
      children: (
        <div className="max-w-xl">
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <h3 className="text-sm font-semibold text-gray-800 mb-4">Notification Preferences</h3>
            <SettingRow label="Signal detected" description="Notify when new signals are found for tracked companies">
              <Switch
                checked={settings.notifications.signal_detected}
                onChange={(v) => handleUpdate('notifications', 'signal_detected', v)}
                loading={saving}
              />
            </SettingRow>
            <SettingRow label="Brief generated" description="Notify when a research brief is ready">
              <Switch
                checked={settings.notifications.brief_generated}
                onChange={(v) => handleUpdate('notifications', 'brief_generated', v)}
                loading={saving}
              />
            </SettingRow>
            <SettingRow label="Contact enriched" description="Notify when contact enrichment completes">
              <Switch
                checked={settings.notifications.contact_enriched}
                onChange={(v) => handleUpdate('notifications', 'contact_enriched', v)}
                loading={saving}
              />
            </SettingRow>
            <SettingRow label="Monitoring complete" description="Notify when scheduled monitoring finishes">
              <Switch
                checked={settings.notifications.monitoring_complete}
                onChange={(v) => handleUpdate('notifications', 'monitoring_complete', v)}
                loading={saving}
              />
            </SettingRow>
          </div>
        </div>
      ),
    },
    {
      key: 'defaults',
      label: 'Defaults',
      children: (
        <div className="max-w-xl space-y-6">
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <h3 className="text-sm font-semibold text-gray-800 mb-4">Outreach Defaults</h3>
            <SettingRow label="Voice profile">
              <Select
                value={settings.outreach_defaults.voice_profile}
                options={VOICE_OPTIONS}
                onChange={(v) => handleUpdate('outreach_defaults', 'voice_profile', v)}
                style={{ width: 160 }}
                size="small"
              />
            </SettingRow>
            <SettingRow label="Tone">
              <Select
                value={settings.outreach_defaults.tone}
                options={TONE_OPTIONS}
                onChange={(v) => handleUpdate('outreach_defaults', 'tone', v)}
                style={{ width: 160 }}
                size="small"
              />
            </SettingRow>
            <SettingRow label="Default format">
              <Select
                value={settings.outreach_defaults.format}
                options={FORMAT_OPTIONS}
                onChange={(v) => handleUpdate('outreach_defaults', 'format', v)}
                style={{ width: 160 }}
                size="small"
              />
            </SettingRow>
          </div>

          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <h3 className="text-sm font-semibold text-gray-800 mb-1">Monitoring Defaults</h3>
            <p className="text-xs text-gray-400 mb-4">Applied as initial values when you first enable monitoring on a tracking list.</p>
            <SettingRow label="Frequency" description="How often to check for new signals">
              <InputNumber
                value={settings.monitoring_defaults.frequency_days}
                min={1}
                max={30}
                addonAfter="days"
                onChange={(v) => v && handleUpdate('monitoring_defaults', 'frequency_days', v)}
                size="small"
                style={{ width: 120 }}
              />
            </SettingRow>
            <SettingRow label="Alert threshold" description="Minimum priority to trigger notifications">
              <Select
                value={settings.monitoring_defaults.alert_threshold}
                options={THRESHOLD_OPTIONS}
                onChange={(v) => handleUpdate('monitoring_defaults', 'alert_threshold', v)}
                style={{ width: 180 }}
                size="small"
              />
            </SettingRow>
          </div>

          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <h3 className="text-sm font-semibold text-gray-800 mb-4">Display</h3>
            <SettingRow label="Show low confidence signals" description="Include low-confidence signals in the feed">
              <Switch
                checked={settings.display.signal_feed_show_low_confidence}
                onChange={(v) => handleUpdate('display', 'signal_feed_show_low_confidence', v)}
                loading={saving}
              />
            </SettingRow>
            <SettingRow label="Activity feed verbosity">
              <Select
                value={settings.display.activity_feed_verbosity}
                options={VERBOSITY_OPTIONS}
                onChange={(v) => handleUpdate('display', 'activity_feed_verbosity', v)}
                style={{ width: 160 }}
                size="small"
              />
            </SettingRow>
          </div>
        </div>
      ),
    },
  ];

  return (
    <div>
      <h1 className="page-title">Settings</h1>
      <Tabs items={items} size="small" className="mt-4" />
    </div>
  );
}
