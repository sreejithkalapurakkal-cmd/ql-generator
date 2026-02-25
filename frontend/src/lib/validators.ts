import * as yup from 'yup';

export const icpProfileSchema = yup.object({
  industries: yup
    .array()
    .of(yup.string().min(1).required())
    .min(1, 'At least one industry required')
    .required(),
  companySizeRange: yup
    .object({
      min: yup.number().integer().min(1).required('Min company size required'),
      max: yup.number().integer().min(1).required('Max company size required'),
    })
    .test('min-max', 'Max must be >= min', (v) => (v?.max ?? 0) >= (v?.min ?? 0)),
  revenueRange: yup
    .object({
      min: yup.number().min(0).required('Min revenue required'),
      max: yup.number().min(0).required('Max revenue required'),
    })
    .test('min-max', 'Max must be >= min', (v) => (v?.max ?? 0) >= (v?.min ?? 0)),
  geographies: yup
    .array()
    .of(yup.string().required())
    .min(1, 'At least one geography required')
    .required(),
  techStack: yup.array().of(yup.string().required()).optional(),
  keywords: yup.array().of(yup.string().required()).optional(),
  additionalNotes: yup.string().max(1000).optional(),
});

export const bantWeightsSchema = yup.object({
  budget: yup.number().min(0).max(1).required(),
  authority: yup.number().min(0).max(1).required(),
  need: yup.number().min(0).max(1).required(),
  timeline: yup.number().min(0).max(1).required(),
});

export const icpFormSchema = yup.object({
  icpProfile: icpProfileSchema,
  bantWeights: bantWeightsSchema,
  maxResults: yup.number().min(1).max(50).required(),
});
