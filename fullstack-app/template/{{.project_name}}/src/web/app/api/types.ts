/**
 * API response types
 */

export interface HealthStatus {
  status: string;
  environment: string;
  version: string;
}

export interface ApiError {
  detail: string;
  status: number;
}

export interface RootResponse {
  message: string;
  docs: string;
}
