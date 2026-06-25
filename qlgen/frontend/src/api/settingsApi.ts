import client from './client';

export interface UserSettings {
  notifications: {
    signal_detected: boolean;
    brief_generated: boolean;
    contact_enriched: boolean;
    monitoring_complete: boolean;
  };
  monitoring_defaults: {
    frequency_days: number;
    signal_types: string[];
    alert_threshold: string;
  };
  outreach_defaults: {
    voice_profile: string;
    tone: string;
    format: string;
  };
  display: {
    signal_feed_show_low_confidence: boolean;
    activity_feed_verbosity: string;
  };
}

export const getSettings = async (): Promise<{ settings: UserSettings; user_id: string }> => {
  const res = await client.get('/settings');
  return res.data;
};

export const updateSettings = async (
  updates: Partial<UserSettings>
): Promise<{ settings: UserSettings; user_id: string }> => {
  const res = await client.patch('/settings', updates);
  return res.data;
};
