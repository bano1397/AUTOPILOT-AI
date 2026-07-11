import { redirect } from "next/navigation";

/** Auth is disabled — the app opens straight to the dashboard. */
export default function HomePage() {
  redirect("/dashboard");
}
