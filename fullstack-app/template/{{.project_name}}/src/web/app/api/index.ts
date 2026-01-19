/**
 * API module exports
 *
 * Usage:
 *   import { api, type HealthStatus } from "@/app/api";
 *
 *   const health = await api.health.check();
 */

export { api, ApiClientError } from "./client";
export type { ApiError, HealthStatus, RootResponse } from "./types";
