/**
 * Centralized API client for making requests to the FastAPI backend.
 *
 * In development: Requests are proxied via Next.js rewrites (/api/* -> localhost:8000/api/*)
 * In production: Frontend is served by FastAPI, so /api/* goes directly to the backend
 */

import type { ApiError, HealthStatus, RootResponse } from "./types";

const API_BASE = "/api";

class ApiClientError extends Error {
  constructor(
    message: string,
    public status: number,
    public detail?: string,
  ) {
    super(message);
    this.name = "ApiClientError";
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail: string | undefined;
    try {
      const error = (await response.json()) as ApiError;
      detail = error.detail;
    } catch {
      // Response body is not JSON
    }
    throw new ApiClientError(
      detail || `HTTP ${response.status}: ${response.statusText}`,
      response.status,
      detail,
    );
  }
  return response.json() as Promise<T>;
}

/**
 * GET request helper
 */
async function get<T>(endpoint: string): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
    },
  });
  return handleResponse<T>(response);
}

/**
 * POST request helper
 */
async function post<T, B = unknown>(endpoint: string, body?: B): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  return handleResponse<T>(response);
}

/**
 * PUT request helper
 */
async function put<T, B = unknown>(endpoint: string, body?: B): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  return handleResponse<T>(response);
}

/**
 * DELETE request helper
 */
async function del<T>(endpoint: string): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    method: "DELETE",
    headers: {
      "Content-Type": "application/json",
    },
  });
  return handleResponse<T>(response);
}

/**
 * API client with typed endpoints
 */
export const api = {
  /** Health check endpoint */
  health: {
    check: () => get<HealthStatus>("/health"),
  },

  /** Root endpoint */
  root: {
    get: () => get<RootResponse>("/"),
  },

  // Add more endpoint groups here as your API grows:
  // users: {
  //   list: () => get<User[]>("/users"),
  //   get: (id: string) => get<User>(`/users/${id}`),
  //   create: (data: CreateUser) => post<User, CreateUser>("/users", data),
  //   update: (id: string, data: UpdateUser) => put<User, UpdateUser>(`/users/${id}`, data),
  //   delete: (id: string) => del<void>(`/users/${id}`),
  // },
};

export { ApiClientError };
export type { ApiError, HealthStatus, RootResponse };
