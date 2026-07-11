import { apiFetch } from "@/lib/api/client";

import type { LoginInput, RegisterInput } from "./schemas";
import type { TokenPair, User } from "./types";

export function login(input: LoginInput): Promise<TokenPair> {
  return apiFetch<TokenPair>("/api/v1/auth/login", {
    method: "POST",
    body: input,
    auth: false,
  });
}

export function register(input: RegisterInput): Promise<User> {
  return apiFetch<User>("/api/v1/auth/register", {
    method: "POST",
    body: { email: input.email, password: input.password },
    auth: false,
  });
}

export function logout(): Promise<unknown> {
  // The refresh token is identified by the httpOnly cookie.
  return apiFetch("/api/v1/auth/logout", {
    method: "POST",
    body: {},
    auth: false,
  });
}

export function getMe(): Promise<User> {
  return apiFetch<User>("/api/v1/auth/me");
}
