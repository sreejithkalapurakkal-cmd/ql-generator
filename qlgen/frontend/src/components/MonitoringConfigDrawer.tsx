import React, { useState, useEffect, useMemo } from 'react';
import { Drawer, Button, Switch, Select, Segmented, InputNumber, Checkbox, Alert, message } from 'antd';
import { ClockCircleOutlined, ThunderboltOutlined } from '@ant-design/icons';
import { configureMonitoring, getSignalTypes, type SignalTypeMetadata, type FrequencyPreset } from '../api/signalApi';
import { getSettings } from '../api/settingsApi';
import { detectSignalsForList } from '../api/trackingApi';
import type { MonitoringConfig, SignalHints } from '../types';
import { SIGNAL_TYPE_LABELS, SIGNAL_ALERT_THRESHOLD_OPTIONS as THRESHOLD_OPTIONS } from '../types';

interface MonitoringConfigDrawerProps {
  open: boolean;
  onClose: () => void;
  listId: string;
  config: MonitoringConfig;
  signalHints?: SignalHints;
  lastMonitoredAt: string | null;
  nextMonitorDue?: string | null;
  onSaved: (config: MonitoringConfig, nextMonitorDue: string | null) => void;
}

const PRESET_OPTIONS = [
  { value: 1, label: 'Daily' },
  { value: 3, label: 'Every 3 days' },
  { value: 7, label: 'Weekly' },
  { value: 14, label: 'Biweekly' },
  { value: 0, label: 'Custom' },
];

const ALL_SIGNAL_TYPES = Object.keys(SIGNAL_TYPE_LABELS);

const FAST_DECAY_TYPES = new Set(['funding', 'earnings_report', 'product_launch', 'competitor_churn', 'press_mention']);

const MonitoringConfigDrawer: React.FC<MonitoringConfigDrawerProps> = ({
  open, onClose, listId, config, signalHints, lastMonitoredAt, nextMonitorDue: nextDueProp, onSaved,
}) => {
  const [enabled, setEnabled] = useState(false);
  const [frequencyDays, setFrequencyDays] = useState(7);
  const [selectedPreset, setSelectedPreset] = useState<number>(7);
  const [signalTypes, setSignalTypes] = useState<string[]>([]);
  const [alertThreshold, setAlertThreshold] = useState('high');
  const [saving, setSaving] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [signalTypeMeta, setSignalTypeMeta] = useState<Record<string, SignalTypeMetadata>>({});
  const [presets, setPresets] = useState<FrequencyPreset[]>([]);
  const [defaultsLoaded, setDefaultsLoaded] = useState(false);

  // Load signal type metadata
  useEffect(() => {
    if (open) {
      getSignalTypes()
        .then((res) => {
          setSignalTypeMeta(res.data.signal_types);
          setPresets(res.data.presets);
        })
        .catch(() => {});
    }
  }, [open]);

  // Initialize form from config or user defaults
  useEffect(() => {
    if (!open) {
      setDefaultsLoaded(false);
      return;
    }

    const hasConfig = config.enabled !== undefined || (config.frequency_days !== undefined && config.frequency_days > 0);

    if (hasConfig) {
      setEnabled(config.enabled ?? false);
      const freq = config.frequency_days ?? 7;
      setFrequencyDays(freq);
      setSelectedPreset(PRESET_OPTIONS.some((p) => p.value === freq) ? freq : 0);
      setSignalTypes(config.signal_types ?? []);
      setAlertThreshold(config.alert_threshold ?? 'high');
      setDefaultsLoaded(true);
    } else if (!defaultsLoaded) {
      // Load user defaults for unconfigured lists
      getSettings()
        .then(({ settings }) => {
          const defaults = settings.monitoring_defaults;
          const freq = defaults.frequency_days || 7;
          setFrequencyDays(freq);
          setSelectedPreset(PRESET_OPTIONS.some((p) => p.value === freq) ? freq : 0);
          setSignalTypes(defaults.signal_types || []);
          setAlertThreshold(defaults.alert_threshold || 'high');
          setEnabled(false);
          setDefaultsLoaded(true);
        })
        .catch(() => {
          setDefaultsLoaded(true);
        });
    }
  }, [open, config, defaultsLoaded]);

  // Smart recommendation based on signal hints
  const recommendation = useMemo(() => {
    const hasBudget = (signalHints?.budget_signals?.length ?? 0) > 0;
    const hasUrgency = (signalHints?.urgency_signals?.length ?? 0) > 0;
    const watchesFastDecay = signalTypes.some((t) => FAST_DECAY_TYPES.has(t));

    if (hasBudget || hasUrgency || watchesFastDecay) {
      const reasons: string[] = [];
      if (hasBudget) reasons.push('budget signals (funding: 2-day half-life)');
      if (hasUrgency) reasons.push('urgency signals (5-day half-life)');
      if (watchesFastDecay && !hasBudget) reasons.push('fast-decay signal types');

      if (frequencyDays > 3) {
        return {
          show: true,
          message: `This list tracks ${reasons.join(' and ')}. Checking every ${frequencyDays} day${frequencyDays > 1 ? 's' : ''} means signals may lose significant strength before detection. We recommend every 3 days or daily.`,
          suggestedDays: 3,
        };
      }
    }
    return { show: false, message: '', suggestedDays: 0 };
  }, [signalHints, signalTypes, frequencyDays]);

  const handlePresetChange = (value: string | number) => {
    const days = Number(value);
    setSelectedPreset(days);
    if (days > 0) {
      setFrequencyDays(days);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const res = await configureMonitoring(listId, {
        enabled,
        frequency_days: frequencyDays,
        signal_types: signalTypes.length > 0 ? signalTypes : undefined,
        alert_threshold: alertThreshold,
      });
      onSaved(
        { enabled, frequency_days: frequencyDays, signal_types: signalTypes, alert_threshold: alertThreshold },
        res.data.next_monitor_due,
      );
      message.success(enabled ? 'Monitoring enabled' : 'Monitoring configuration saved');
      onClose();
    } catch {
      message.error('Failed to save monitoring configuration');
    } finally {
      setSaving(false);
    }
  };

  const handleScanNow = async () => {
    setScanning(true);
    try {
      await detectSignalsForList(listId);
      message.success('Signal detection started');
    } catch {
      message.error('Failed to start signal detection');
    } finally {
      setScanning(false);
    }
  };

  const formatTimestamp = (iso: string | null) => {
    if (!iso) return 'Never';
    return new Date(iso).toLocaleString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric',
      hour: 'numeric', minute: '2-digit',
    });
  };

  return (
    <Drawer
      title={
        <div>
          <div className="text-base font-bold text-gray-900">Monitoring Schedule</div>
          <div className="text-xs text-gray-400 font-normal mt-0.5">
            Automatically scan for new signals on a recurring schedule
          </div>
        </div>
      }
      open={open}
      onClose={onClose}
      width={480}
      styles={{ body: { padding: '16px 24px' } }}
      extra={
        <Button type="primary" onClick={handleSave} loading={saving} size="small">
          Save
        </Button>
      }
    >
      <div className="space-y-6">
        {/* Enable toggle */}
        <div className="flex items-center justify-between py-3 px-4 bg-gray-50 rounded-lg">
          <div>
            <div className="text-sm font-semibold text-gray-900">Enable Automatic Monitoring</div>
            <div className="text-xs text-gray-500 mt-0.5">
              {enabled ? 'Signals will be scanned on schedule' : 'No automatic scanning'}
            </div>
          </div>
          <Switch checked={enabled} onChange={setEnabled} />
        </div>

        {/* Frequency presets */}
        <div className={enabled ? '' : 'opacity-50 pointer-events-none'}>
          <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
            Scan Frequency
          </label>
          <Segmented
            options={PRESET_OPTIONS}
            value={selectedPreset}
            onChange={handlePresetChange}
            block
            className="mb-2"
          />
          {selectedPreset === 0 && (
            <div className="flex items-center gap-2 mt-2">
              <InputNumber
                value={frequencyDays}
                min={1}
                max={30}
                onChange={(v) => v && setFrequencyDays(v)}
                size="small"
                className="!w-20"
              />
              <span className="text-sm text-gray-500">days</span>
            </div>
          )}

          {/* Preset descriptions */}
          <div className="text-xs text-gray-400 mt-2">
            {frequencyDays === 1 && 'Best for key accounts and active deals — catches fast-decaying signals like funding and earnings.'}
            {frequencyDays === 3 && 'Good for pipeline accounts — balances signal freshness with API usage.'}
            {frequencyDays === 7 && 'Standard for named accounts — suitable for executive changes and partnerships.'}
            {frequencyDays === 14 && 'For territory watch — only catches slow-moving signals like tech adoption.'}
            {frequencyDays > 14 && 'Long interval — many signal types will have fully decayed between scans.'}
          </div>
        </div>

        {/* Smart recommendation banner */}
        {recommendation.show && enabled && (
          <Alert
            type="info"
            showIcon
            icon={<ThunderboltOutlined />}
            message="Frequency Recommendation"
            description={
              <div>
                <p className="text-xs mb-2">{recommendation.message}</p>
                <Button
                  size="small"
                  type="link"
                  className="!p-0 !h-auto"
                  onClick={() => {
                    setFrequencyDays(recommendation.suggestedDays);
                    setSelectedPreset(recommendation.suggestedDays);
                  }}
                >
                  Switch to every {recommendation.suggestedDays} days
                </Button>
              </div>
            }
          />
        )}

        {/* Signal types to monitor */}
        <div className={enabled ? '' : 'opacity-50 pointer-events-none'}>
          <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
            Signal Types to Monitor
          </label>
          <div className="text-xs text-gray-400 mb-2">
            Leave empty to monitor all types. Select specific types to narrow the scan.
          </div>
          <Checkbox.Group
            value={signalTypes}
            onChange={(vals) => setSignalTypes(vals as string[])}
            className="!flex flex-wrap gap-x-1 gap-y-2"
          >
            {ALL_SIGNAL_TYPES.map((type) => {
              const meta = signalTypeMeta[type];
              const halfLife = meta?.half_life_days;
              return (
                <Checkbox key={type} value={type} className="!ml-0">
                  <span className="text-xs">
                    {SIGNAL_TYPE_LABELS[type]}
                    {halfLife !== undefined && (
                      <span className="text-gray-400 ml-1">({halfLife}d)</span>
                    )}
                  </span>
                </Checkbox>
              );
            })}
          </Checkbox.Group>
        </div>

        {/* Alert threshold */}
        <div className={enabled ? '' : 'opacity-50 pointer-events-none'}>
          <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
            Alert Threshold
          </label>
          <div className="text-xs text-gray-400 mb-2">
            Minimum priority level to trigger notifications.
          </div>
          <Select
            value={alertThreshold}
            options={THRESHOLD_OPTIONS}
            onChange={setAlertThreshold}
            style={{ width: 200 }}
            size="small"
          />
        </div>

        {/* Status display */}
        <div className="bg-gray-50 rounded-lg p-4 space-y-2">
          <div className="flex items-center gap-2 text-xs">
            <ClockCircleOutlined className="text-gray-400" />
            <span className="text-gray-500">Last scanned:</span>
            <span className="text-gray-700 font-medium">{formatTimestamp(lastMonitoredAt)}</span>
          </div>
          {nextDueProp && (
            <div className="flex items-center gap-2 text-xs">
              <ClockCircleOutlined className="text-gray-400" />
              <span className="text-gray-500">Next scheduled:</span>
              <span className="text-gray-700 font-medium">{formatTimestamp(nextDueProp)}</span>
            </div>
          )}
        </div>

        {/* Scan Now button */}
        <Button
          icon={<ThunderboltOutlined />}
          onClick={handleScanNow}
          loading={scanning}
          block
          className="!rounded-lg"
        >
          Scan Now
        </Button>
      </div>
    </Drawer>
  );
};

export default MonitoringConfigDrawer;
