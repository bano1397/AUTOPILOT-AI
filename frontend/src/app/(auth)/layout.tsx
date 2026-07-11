import { redirect } from "next/navigation";

/**
 * Authentication is disabled for the public demo, so the login/register routes
 * are neutralized — any visit is redirected into the app.
 */
export default function AuthLayout() {
  redirect("/dashboard");
}
