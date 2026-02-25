import React, { useState, useEffect } from 'react';
import {
  Box, Typography, Button, Paper, TextField, Select, MenuItem,
  FormControl, InputLabel, Chip, Stack, Divider, Snackbar, Alert,
  Stepper, Step, StepLabel, StepButton, Table, TableBody, TableRow, TableCell,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import CloseIcon from '@mui/icons-material/Close';
import { useNavigate, useParams } from 'react-router-dom';
import { createICP, getICP, updateICP } from '../api/icpApi';
import { startPipeline } from '../api/pipelineApi';
import { ICPDefinition, DEFAULT_ICP } from '../types';

// ─── Tag Input Component ───────────────────────────────────────────────────────
interface TagInputProps {
  label: string;
  hint?: string;
  values: string[];
  onChange: (vals: string[]) => void;
  placeholder?: string;
  field: string;
}

const TagInputField: React.FC<TagInputProps> = ({ label, hint, values, onChange, placeholder, field }) => {
  const [input, setInput] = useState('');

  const add = () => {
    const v = input.trim();
    if (v && !values.includes(v)) {
      onChange([...values, v]);
      setInput('');
    }
  };

  const remove = (tag: string) => onChange(values.filter((t) => t !== tag));

  return (
    <Box sx={{ mb: '22px' }}>
      <Typography sx={{ fontSize: 13.5, fontWeight: 600, color: '#3D3D3D', mb: hint ? '4px' : '6px', letterSpacing: '-0.1px' }}>
        {label}
      </Typography>
      {hint && (
        <Typography sx={{ fontSize: 12, color: '#ADADAD', mb: '8px', lineHeight: 1.5 }}>
          {hint}
        </Typography>
      )}
      <Box
        sx={{
          display: 'flex', flexWrap: 'wrap', gap: 0.5,
          p: '6px 8px',
          border: '1px solid #D6D6D6', borderRadius: '6px',
          minHeight: 42, alignItems: 'center',
          bgcolor: '#fff',
          transition: 'border .15s, box-shadow .15s',
          '&:focus-within': {
            borderColor: '#5C2D8F',
            boxShadow: '0 0 0 3px rgba(92,45,143,.12)',
          },
        }}
      >
        {values.map((v) => (
          <Chip
            key={v}
            label={v}
            size="small"
            onDelete={() => remove(v)}
            deleteIcon={<CloseIcon sx={{ fontSize: '13px !important' }} />}
            sx={{
              bgcolor: '#F5F5F5', color: '#5C5C5C',
              border: '1px solid #EBEBEB', borderRadius: '6px',
              fontSize: 12, height: 24,
              '& .MuiChip-deleteIcon': { color: '#858585', '&:hover': { color: '#D93025' } },
            }}
          />
        ))}
        <Box
          component="input"
          placeholder={placeholder || `Add ${label.toLowerCase()} and press Enter`}
          value={input}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => setInput(e.target.value)}
          onKeyDown={(e: React.KeyboardEvent<HTMLInputElement>) => { if (e.key === 'Enter') { e.preventDefault(); add(); } }}
          sx={{
            border: 'none', outline: 'none',
            fontSize: 13, flex: 1, minWidth: 120,
            p: '2px 0', background: 'transparent',
            fontFamily: "'DM Sans', sans-serif",
            color: '#242424',
          }}
        />
        {input.trim() && (
          <Button
            size="small"
            onClick={add}
            sx={{ color: '#5C2D8F', fontSize: 12, minWidth: 'auto', px: 1, py: 0.25 }}
          >
            Add
          </Button>
        )}
      </Box>
    </Box>
  );
};

// ─── Steps ────────────────────────────────────────────────────────────────────
const ICPConfigPage: React.FC = () => {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const [current, setCurrent] = useState(0);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [config, setConfig] = useState<ICPDefinition>({ ...DEFAULT_ICP });
  const [saving, setSaving] = useState(false);
  const [snack, setSnack] = useState({ open: false, msg: '', severity: 'success' as 'success' | 'error' });

  useEffect(() => {
    if (id) {
      getICP(id).then((res) => {
        setName(res.data.name);
        setDescription(res.data.description || '');
        setConfig(res.data.config as unknown as ICPDefinition);
      });
    }
  }, [id]);

  const fieldLabel = (label: string, hint?: string) => (
    <Box sx={{ mb: hint ? '4px' : '6px' }}>
      <Typography sx={{ fontSize: 13.5, fontWeight: 600, color: '#3D3D3D', letterSpacing: '-0.1px' }}>
        {label}
      </Typography>
      {hint && (
        <Typography sx={{ fontSize: 12, color: '#ADADAD', mt: '4px', lineHeight: 1.5 }}>
          {hint}
        </Typography>
      )}
    </Box>
  );

  const steps = [
    {
      title: 'Offering',
      content: (
        <Stack spacing={0}>
          <Box sx={{ mb: '22px' }}>
            {fieldLabel('ICP Name', 'A short, memorable name for this configuration.')}
            <TextField
              fullWidth
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., MidMarket US ECommerce 2026"
              required
            />
          </Box>
          <Box sx={{ mb: '22px' }}>
            {fieldLabel('Description')}
            <TextField
              fullWidth multiline rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Brief description of this ICP..."
            />
          </Box>
          <TagInputField
            label="Target Offerings / Service Areas"
            field="offerings"
            values={config.target_offering}
            onChange={(v) => setConfig({ ...config, target_offering: v })}
            placeholder="e.g., Platform engineering & replatforming"
          />
        </Stack>
      ),
    },
    {
      title: 'Regions',
      content: (
        <Stack spacing={0}>
          <TagInputField
            label="Target Countries"
            field="countries"
            values={config.regions.countries}
            onChange={(v) => setConfig({ ...config, regions: { ...config.regions, countries: v } })}
            placeholder="e.g., United States"
          />
          <TagInputField
            label="Priority Areas (States, Cities)"
            field="priority_areas"
            values={config.regions.priority_areas}
            onChange={(v) => setConfig({ ...config, regions: { ...config.regions, priority_areas: v } })}
            placeholder="e.g., California, New York"
          />
        </Stack>
      ),
    },
    {
      title: 'Industry',
      content: (
        <Box>
          {fieldLabel('Industry Verticals', 'Add the industry verticals you are targeting.')}
          <Stack spacing={1.5} sx={{ mt: 1 }}>
            {config.industry_types.map((ind, i) => (
              <Box key={i} sx={{ display: 'flex', gap: 1.5, alignItems: 'center' }}>
                <TextField
                  value={ind.vertical}
                  onChange={(e) => {
                    const updated = [...config.industry_types];
                    updated[i] = { ...updated[i], vertical: e.target.value };
                    setConfig({ ...config, industry_types: updated });
                  }}
                  placeholder="Vertical"
                  sx={{ flex: 1 }}
                />
                <TextField
                  value={ind.sub_vertical || ''}
                  onChange={(e) => {
                    const updated = [...config.industry_types];
                    updated[i] = { ...updated[i], sub_vertical: e.target.value || null };
                    setConfig({ ...config, industry_types: updated });
                  }}
                  placeholder="Sub-vertical (optional)"
                  sx={{ flex: 1 }}
                />
                <Button
                  variant="outlined"
                  size="small"
                  onClick={() => setConfig({ ...config, industry_types: config.industry_types.filter((_, j) => j !== i) })}
                  sx={{ borderColor: '#EBEBEB', color: '#D93025', minWidth: 'auto', px: 1, '&:hover': { borderColor: '#D93025', bgcolor: '#FDECEA' } }}
                >
                  <CloseIcon sx={{ fontSize: 14 }} />
                </Button>
              </Box>
            ))}
            <Button
              variant="outlined"
              startIcon={<AddIcon />}
              onClick={() => setConfig({ ...config, industry_types: [...config.industry_types, { vertical: '', sub_vertical: null }] })}
              sx={{ borderStyle: 'dashed', borderColor: '#D6D6D6', color: '#858585', alignSelf: 'flex-start', '&:hover': { borderColor: '#5C2D8F', color: '#5C2D8F', bgcolor: '#F4EFFE' } }}
            >
              Add Industry
            </Button>
          </Stack>
        </Box>
      ),
    },
    {
      title: 'Size',
      content: (
        <Stack spacing={0}>
          <Box sx={{ mb: '22px' }}>
            {fieldLabel('Employee Count Range')}
            <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', mt: 1 }}>
              <TextField
                type="number"
                label="Min"
                value={config.company_size.employees_min}
                onChange={(e) => setConfig({ ...config, company_size: { ...config.company_size, employees_min: Number(e.target.value) || 1 } })}
                sx={{ width: 140 }}
                inputProps={{ min: 1 }}
              />
              <Typography sx={{ color: '#ADADAD', fontWeight: 500 }}>to</Typography>
              <TextField
                type="number"
                label="Max"
                value={config.company_size.employees_max}
                onChange={(e) => setConfig({ ...config, company_size: { ...config.company_size, employees_max: Number(e.target.value) || 10000 } })}
                sx={{ width: 140 }}
                inputProps={{ min: 1 }}
              />
            </Box>
          </Box>
          <Box sx={{ mb: '22px' }}>
            {fieldLabel('Revenue Range')}
            <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', mt: 1, flexWrap: 'wrap' }}>
              <FormControl size="small" sx={{ width: 90 }}>
                <InputLabel>Currency</InputLabel>
                <Select
                  value={config.company_size.revenue_currency}
                  label="Currency"
                  onChange={(e) => setConfig({ ...config, company_size: { ...config.company_size, revenue_currency: e.target.value } })}
                >
                  <MenuItem value="USD">USD</MenuItem>
                  <MenuItem value="INR">INR</MenuItem>
                  <MenuItem value="EUR">EUR</MenuItem>
                  <MenuItem value="GBP">GBP</MenuItem>
                </Select>
              </FormControl>
              <TextField
                type="number"
                label="Min Revenue"
                value={config.company_size.revenue_min}
                onChange={(e) => setConfig({ ...config, company_size: { ...config.company_size, revenue_min: Number(e.target.value) || 0 } })}
                sx={{ width: 180 }}
                inputProps={{ min: 0 }}
              />
              <Typography sx={{ color: '#ADADAD', fontWeight: 500 }}>to</Typography>
              <TextField
                type="number"
                label="Max Revenue"
                value={config.company_size.revenue_max}
                onChange={(e) => setConfig({ ...config, company_size: { ...config.company_size, revenue_max: Number(e.target.value) || 0 } })}
                sx={{ width: 180 }}
                inputProps={{ min: 0 }}
              />
            </Box>
          </Box>
        </Stack>
      ),
    },
    {
      title: 'Tech',
      content: (
        <Stack spacing={0}>
          <TagInputField
            label="Technology Maturity Signals (Positive)"
            field="tech_signals"
            values={config.technology_maturity.signals}
            onChange={(v) => setConfig({ ...config, technology_maturity: { ...config.technology_maturity, signals: v } })}
            placeholder="e.g., Running on Shopify Plus"
          />
          <TagInputField
            label="Negative Signals (Migration Needs)"
            field="tech_negative"
            values={config.technology_maturity.negative_signals}
            onChange={(v) => setConfig({ ...config, technology_maturity: { ...config.technology_maturity, negative_signals: v } })}
            placeholder="e.g., Legacy Magento 1 migration overdue"
          />
        </Stack>
      ),
    },
    {
      title: 'Infra',
      content: (
        <TagInputField
          label="Infrastructure Readiness Indicators"
          field="infra"
          values={config.infrastructure_readiness.indicators}
          onChange={(v) => setConfig({ ...config, infrastructure_readiness: { indicators: v } })}
          placeholder="e.g., Cloud-hosted storefront"
        />
      ),
    },
    {
      title: 'Drivers',
      content: (
        <Stack spacing={0}>
          <TagInputField
            label="Growth Triggers"
            field="growth"
            values={config.digital_transformation_drivers.growth_triggers}
            onChange={(v) => setConfig({ ...config, digital_transformation_drivers: { ...config.digital_transformation_drivers, growth_triggers: v } })}
            placeholder="e.g., YoY revenue growth >20%"
          />
          <TagInputField
            label="Operational Pains"
            field="pains"
            values={config.digital_transformation_drivers.operational_pains}
            onChange={(v) => setConfig({ ...config, digital_transformation_drivers: { ...config.digital_transformation_drivers, operational_pains: v } })}
            placeholder="e.g., Site performance degrading during peak traffic"
          />
          <TagInputField
            label="Competitive Pressures"
            field="pressures"
            values={config.digital_transformation_drivers.competitive_pressures}
            onChange={(v) => setConfig({ ...config, digital_transformation_drivers: { ...config.digital_transformation_drivers, competitive_pressures: v } })}
            placeholder="e.g., Rising CAC"
          />
          <TagInputField
            label="Strategic Initiatives"
            field="initiatives"
            values={config.digital_transformation_drivers.strategic_initiatives}
            onChange={(v) => setConfig({ ...config, digital_transformation_drivers: { ...config.digital_transformation_drivers, strategic_initiatives: v } })}
            placeholder="e.g., Launching mobile app or PWA"
          />
        </Stack>
      ),
    },
    {
      title: 'Leadership',
      content: (
        <Stack spacing={0}>
          <TagInputField
            label="Target Roles"
            field="roles"
            values={config.leadership_traits.target_roles}
            onChange={(v) => setConfig({ ...config, leadership_traits: { ...config.leadership_traits, target_roles: v } })}
            placeholder="e.g., CTO, VP of Engineering"
          />
          <TagInputField
            label="Behavioral Traits"
            field="traits"
            values={config.leadership_traits.behavioral_traits}
            onChange={(v) => setConfig({ ...config, leadership_traits: { ...config.leadership_traits, behavioral_traits: v } })}
            placeholder="e.g., Data-driven decision maker"
          />
        </Stack>
      ),
    },
    {
      title: 'Review',
      content: (
        <Box>
          <Typography sx={{ fontSize: 15, fontWeight: 700, color: '#141414', mb: 2, letterSpacing: '-0.2px' }}>
            ICP Summary
          </Typography>
          <Paper variant="outlined" sx={{ border: '1px solid #EBEBEB', boxShadow: 'none', borderRadius: '8px', overflow: 'hidden' }}>
            <Table size="small">
              <TableBody>
                {[
                  { label: 'Name', value: name || '(unnamed)' },
                  { label: 'Description', value: description || '-' },
                  { label: 'Target Offerings', value: config.target_offering.join(', ') || '-' },
                  { label: 'Regions', value: [config.regions.countries.join(', '), config.regions.priority_areas.join(', ')].filter(Boolean).join(' | ') || '-' },
                  { label: 'Industries', value: config.industry_types.map((i) => i.vertical).join(', ') || '-' },
                  { label: 'Company Size', value: `${config.company_size.employees_min}–${config.company_size.employees_max} employees, ${config.company_size.revenue_currency} ${config.company_size.revenue_min.toLocaleString()}–${config.company_size.revenue_max.toLocaleString()}` },
                  { label: 'Tech Signals', value: config.technology_maturity.signals.join(', ') || '-' },
                  { label: 'Infrastructure', value: config.infrastructure_readiness.indicators.join(', ') || '-' },
                  { label: 'Target Roles', value: config.leadership_traits.target_roles.join(', ') || '-' },
                ].map(({ label, value }) => (
                  <TableRow key={label}>
                    <TableCell
                      sx={{
                        width: 160, fontSize: '11px', fontWeight: 600, textTransform: 'uppercase',
                        letterSpacing: '0.06em', color: '#858585', bgcolor: '#FAFAFA',
                        borderRight: '1px solid #EBEBEB',
                      }}
                    >
                      {label}
                    </TableCell>
                    <TableCell sx={{ fontSize: 13.5, color: '#3D3D3D' }}>
                      {value}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Paper>
        </Box>
      ),
    },
  ];

  const handleSave = async (runPipeline: boolean) => {
    if (!name.trim()) {
      setSnack({ open: true, msg: 'Please provide an ICP name', severity: 'error' });
      return;
    }
    setSaving(true);
    try {
      let icpId = id;
      if (id) {
        await updateICP(id, { name, description, config: config as unknown as Record<string, unknown> });
      } else {
        const res = await createICP({ name, description, config: config as unknown as Record<string, unknown> });
        icpId = res.data.id;
      }
      setSnack({ open: true, msg: 'ICP saved successfully', severity: 'success' });

      if (runPipeline && icpId) {
        const runRes = await startPipeline({ icp_config_id: icpId, options: { max_companies: 15, max_contacts_per_company: 5 } });
        navigate(`/pipeline/${runRes.data.id}`);
      } else {
        navigate('/icp');
      }
    } catch (err: any) {
      setSnack({ open: true, msg: err?.response?.data?.detail || 'Failed to save ICP', severity: 'error' });
    } finally {
      setSaving(false);
    }
  };

  return (
    <Box>
      {/* Page header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 3 }}>
        <Box>
          <Typography sx={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.14em', color: '#F4693B', mb: '5px' }}>
            ICP Builder
          </Typography>
          <Typography sx={{ fontSize: 22, fontWeight: 700, color: '#141414', letterSpacing: '-0.3px' }}>
            {id ? 'Edit ICP Configuration' : 'New ICP Configuration'}
          </Typography>
        </Box>
        <Button
          variant="outlined"
          onClick={() => navigate('/icp')}
          sx={{ borderColor: '#D6D6D6', color: '#3D3D3D', '&:hover': { borderColor: '#ADADAD', bgcolor: '#FAFAFA' } }}
        >
          Cancel
        </Button>
      </Box>

      {/* Builder layout: stepper left + form right */}
      <Box sx={{ display: 'flex', gap: 6 }}>
        {/* Stepper sidebar */}
        <Box sx={{ width: 210, flexShrink: 0 }}>
          <Stepper
            nonLinear
            activeStep={current}
            orientation="vertical"
            sx={{
              '& .MuiStepConnector-line': { borderColor: '#EBEBEB', borderLeftWidth: 2, ml: '6px' },
              '& .MuiStepConnector-root.Mui-active .MuiStepConnector-line': { borderColor: '#5C2D8F' },
              '& .MuiStepConnector-root.Mui-completed .MuiStepConnector-line': { borderColor: '#1E9B6B' },
            }}
          >
            {steps.map((step, index) => (
              <Step key={step.title} completed={index < current}>
                <StepButton
                  onClick={() => setCurrent(index)}
                  sx={{
                    p: '8px 0',
                    '& .MuiStepLabel-label': {
                      fontSize: 13,
                      fontWeight: index === current ? 600 : 500,
                      color: index === current ? '#242424' : index < current ? '#1E9B6B' : '#ADADAD',
                    },
                    '& .MuiStepIcon-root': {
                      color: index < current ? '#1E9B6B' : index === current ? '#5C2D8F' : '#EBEBEB',
                      fontSize: 28,
                    },
                    '& .MuiStepIcon-root.Mui-active': { color: '#5C2D8F' },
                    '& .MuiStepIcon-root.Mui-completed': { color: '#1E9B6B' },
                    '& .MuiStepIcon-text': { fontSize: '0.6rem', fontWeight: 700 },
                  }}
                >
                  <StepLabel>{step.title}</StepLabel>
                </StepButton>
              </Step>
            ))}
          </Stepper>
        </Box>

        {/* Form content */}
        <Box sx={{ flex: 1, maxWidth: 720 }}>
          <Paper
            sx={{
              p: '28px 32px',
              borderRadius: '10px',
              border: '1px solid #EBEBEB',
              boxShadow: '0 1px 4px rgba(0,0,0,.07),0 4px 12px rgba(0,0,0,.04)',
              minHeight: 300,
            }}
          >
            {steps[current].content}
          </Paper>

          {/* Navigation */}
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 3, pt: '20px', borderTop: '1px solid #EBEBEB' }}>
            <Box>
              {current > 0 && (
                <Button
                  variant="outlined"
                  onClick={() => setCurrent((c) => c - 1)}
                  sx={{ borderColor: '#D6D6D6', color: '#3D3D3D', '&:hover': { borderColor: '#ADADAD', bgcolor: '#FAFAFA' } }}
                >
                  Previous
                </Button>
              )}
            </Box>
            <Box sx={{ display: 'flex', gap: 1 }}>
              {current < steps.length - 1 && (
                <Button
                  variant="contained"
                  onClick={() => setCurrent((c) => c + 1)}
                  sx={{ bgcolor: '#5C2D8F', '&:hover': { bgcolor: '#4a2272' } }}
                >
                  Next
                </Button>
              )}
              {current === steps.length - 1 && (
                <>
                  <Button
                    variant="outlined"
                    onClick={() => handleSave(false)}
                    disabled={saving}
                    sx={{ borderColor: '#D6D6D6', color: '#3D3D3D', '&:hover': { borderColor: '#ADADAD', bgcolor: '#FAFAFA' } }}
                  >
                    Save Only
                  </Button>
                  <Button
                    variant="contained"
                    onClick={() => handleSave(true)}
                    disabled={saving}
                    sx={{ bgcolor: '#5C2D8F', '&:hover': { bgcolor: '#4a2272' } }}
                  >
                    {saving ? 'Saving…' : 'Save & Run Pipeline'}
                  </Button>
                </>
              )}
            </Box>
          </Box>
        </Box>
      </Box>

      <Snackbar
        open={snack.open}
        autoHideDuration={3000}
        onClose={() => setSnack((s) => ({ ...s, open: false }))}
        anchorOrigin={{ vertical: 'top', horizontal: 'right' }}
      >
        <Alert severity={snack.severity}>{snack.msg}</Alert>
      </Snackbar>
    </Box>
  );
};

export default ICPConfigPage;
