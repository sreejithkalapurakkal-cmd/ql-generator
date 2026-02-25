import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import {
  Box,
  Button,
  Card,
  CardContent,
  Stepper,
  Step,
  StepLabel,
  TextField,
  Typography,
  Alert,
} from '@mui/material';
import { useNavigate } from 'react-router-dom';
import CompanyProfileSection from './CompanyProfileSection';
import TechStackSection from './TechStackSection';
import GeographySection from './GeographySection';
import BANTWeightsSection from './BANTWeightsSection';
import FormSummaryCard from './FormSummaryCard';
import { useJobSubmit } from '../../hooks/useJobSubmit';
import { icpFormSchema } from '../../lib/validators';
import type { ICPFormData } from '../../types/icp';

const steps = ['Company Profile', 'Tech & Geography', 'BANT Weights', 'Review & Submit'];

const defaultValues: ICPFormData = {
  icpProfile: {
    industries: [],
    companySizeRange: { min: 50, max: 500 },
    revenueRange: { min: 1000000, max: 50000000 },
    geographies: [],
    techStack: [],
    keywords: [],
    additionalNotes: '',
  },
  bantWeights: {
    budget: 0.25,
    authority: 0.25,
    need: 0.25,
    timeline: 0.25,
  },
  maxResults: 25,
};

export default function ICPFormPage() {
  const [activeStep, setActiveStep] = useState(0);
  const navigate = useNavigate();
  const { submitJob, loading, error } = useJobSubmit();

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    trigger,
    formState: { errors },
  } = useForm<ICPFormData>({
    defaultValues,
    resolver: yupResolver(icpFormSchema) as never,
  });

  const formData = watch();

  const handleNext = async () => {
    let valid = true;
    if (activeStep === 0) {
      valid = await trigger(['icpProfile.industries', 'icpProfile.companySizeRange', 'icpProfile.revenueRange']);
    } else if (activeStep === 1) {
      valid = await trigger(['icpProfile.geographies']);
    } else if (activeStep === 2) {
      valid = await trigger(['bantWeights']);
    }
    if (valid) setActiveStep((prev) => prev + 1);
  };

  const handleBack = () => setActiveStep((prev) => prev - 1);

  const onSubmit = async (data: ICPFormData) => {
    const job = await submitJob(data);
    if (job) {
      navigate('/jobs');
    }
  };

  return (
    <Box maxWidth={800} mx="auto">
      <Typography variant="h4" gutterBottom>
        New Lead Search
      </Typography>
      <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
        Define your Ideal Customer Profile (ICP) to discover and score qualified leads.
      </Typography>

      <Stepper activeStep={activeStep} sx={{ mb: 4 }}>
        {steps.map((label) => (
          <Step key={label}>
            <StepLabel>{label}</StepLabel>
          </Step>
        ))}
      </Stepper>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>
      )}

      <Card>
        <CardContent sx={{ p: 3 }}>
          <form onSubmit={handleSubmit(onSubmit)}>
            {activeStep === 0 && (
              <CompanyProfileSection
                register={register}
                setValue={setValue}
                watch={watch}
                errors={errors}
              />
            )}

            {activeStep === 1 && (
              <Box display="flex" flexDirection="column" gap={3}>
                <TechStackSection setValue={setValue} watch={watch} />
                <GeographySection setValue={setValue} watch={watch} errors={errors} />
                <Box>
                  <Typography variant="h6" gutterBottom>Keywords</Typography>
                  <TextField
                    label="Keywords (comma-separated)"
                    {...register('icpProfile.additionalNotes')}
                    fullWidth
                    size="small"
                    multiline
                    rows={2}
                    helperText="Additional search terms or notes"
                  />
                </Box>
                <TextField
                  label="Max Results"
                  type="number"
                  {...register('maxResults', { valueAsNumber: true })}
                  size="small"
                  sx={{ maxWidth: 200 }}
                />
              </Box>
            )}

            {activeStep === 2 && (
              <BANTWeightsSection setValue={setValue} watch={watch} />
            )}

            {activeStep === 3 && (
              <FormSummaryCard data={formData} />
            )}

            <Box display="flex" justifyContent="space-between" mt={3}>
              <Button
                disabled={activeStep === 0}
                onClick={handleBack}
                variant="outlined"
              >
                Back
              </Button>

              {activeStep < steps.length - 1 ? (
                <Button variant="contained" onClick={handleNext}>
                  Next
                </Button>
              ) : (
                <Button
                  type="submit"
                  variant="contained"
                  color="primary"
                  disabled={loading}
                >
                  {loading ? 'Submitting...' : 'Start Search'}
                </Button>
              )}
            </Box>
          </form>
        </CardContent>
      </Card>
    </Box>
  );
}
