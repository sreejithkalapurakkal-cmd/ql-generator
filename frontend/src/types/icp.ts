export interface RangeValue {
  min: number;
  max: number;
}

export interface ICPProfile {
  industries: string[];
  companySizeRange: RangeValue;
  revenueRange: RangeValue;
  geographies: string[];
  techStack: string[];
  keywords: string[];
  additionalNotes: string;
}

export interface BANTWeights {
  budget: number;
  authority: number;
  need: number;
  timeline: number;
}

export interface ICPFormData {
  icpProfile: ICPProfile;
  bantWeights: BANTWeights;
  maxResults: number;
}
