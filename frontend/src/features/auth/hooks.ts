import { useMutation } from "@tanstack/react-query";

import { useAuthStore } from "@/lib/auth/store";
import { useChatStore } from "@/lib/chat/store";

import { getMe, login, logout, register } from "./api";
import type { LoginInput, RegisterInput } from "./schemas";

/** Authenticate, store the session (access token + user). */
export function useLogin() {
  return useMutation({
    mutationFn: async (input: LoginInput) => {
      const tokens = await login(input);
      // Set the access token first so getMe() is authorized; the refresh
      // token lives only in the httpOnly cookie the backend just set.
      useAuthStore.getState().setAccessToken(tokens.access_token);
      const user = await getMe();
      useAuthStore.getState().setSession({
        accessToken: tokens.access_token,
        user,
      });
      return user;
    },
  });
}

/** Create a new account. */
export function useRegister() {
  return useMutation({
    mutationFn: (input: RegisterInput) => register(input),
  });
}

/** Revoke the refresh cookie server-side and clear local session state. */
export function useLogout() {
  return useMutation({
    mutationFn: () => logout(),
    onSettled: () => {
      useAuthStore.getState().clear();
      // Conversations belong to the session that created them.
      useChatStore.getState().clearAll();
    },
  });
}
