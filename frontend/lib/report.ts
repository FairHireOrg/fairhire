import type { FitnessResult } from "./api";

export type ResumeReport = FitnessResult & { sourcePdfId?: string };

export const REPORT_KEY = "fairhire:report:v1";

