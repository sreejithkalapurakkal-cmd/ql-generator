export interface BANTScore {
  budget: number;
  authority: number;
  need: number;
  timeline: number;
  total: number;
  reasoning: string;
}

export interface Lead {
  id: string;
  companyName: string;
  domain: string;
  industry: string;
  employeeCount: number | null;
  estimatedRevenue: number | null;
  location: string | null;
  description: string | null;
  techStack: string[];
  fundingStage: string | null;
  linkedinUrl: string | null;
  bantScore: BANTScore;
  rank: number;
}
