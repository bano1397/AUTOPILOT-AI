"use client";

import {
  Cpu,
  Info,
  type LucideIcon,
  Palette,
  Server,
  SlidersHorizontal,
  User as UserIcon,
} from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  usePreferences,
  useUpdatePreferences,
} from "@/features/preferences/hooks";
import { useHealth } from "@/features/system/hooks";
import { useWorkspaceUser } from "@/features/workspace/hooks";
import { API_URL } from "@/lib/config";
import { cn } from "@/lib/utils";

type Section =
  | "profile"
  | "appearance"
  | "workspace"
  | "models"
  | "system"
  | "about";

const NAV: { key: Section; label: string; icon: LucideIcon }[] = [
  { key: "profile", label: "Profile", icon: UserIcon },
  { key: "appearance", label: "Appearance", icon: Palette },
  { key: "workspace", label: "Workspace", icon: SlidersHorizontal },
  { key: "models", label: "AI Models", icon: Cpu },
  { key: "system", label: "System", icon: Server },
  { key: "about", label: "About", icon: Info },
];

const THEMES = [
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
  { value: "system", label: "System" },
];

function Row({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-4 border-b py-3 last:border-b-0">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm font-medium">{children}</span>
    </div>
  );
}

export default function SettingsPage() {
  const [section, setSection] = useState<Section>("profile");
  const { data: user } = useWorkspaceUser();
  const { theme, setTheme } = useTheme();
  const preferences = usePreferences();
  const savePreferences = useUpdatePreferences();
  const health = useHealth();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="text-muted-foreground">
          Appearance and platform configuration for this workspace.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-[14rem_1fr]">
        {/* Section nav */}
        <nav className="flex gap-1 overflow-x-auto lg:flex-col lg:overflow-visible">
          {NAV.map((item) => (
            <button
              key={item.key}
              type="button"
              onClick={() => setSection(item.key)}
              className={cn(
                "flex shrink-0 items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                section === item.key
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:bg-accent hover:text-foreground",
              )}
            >
              <item.icon className="size-4" />
              {item.label}
            </button>
          ))}
        </nav>

        {/* Panels */}
        <div className="max-w-2xl">
          {section === "profile" && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Profile</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="mb-4 flex items-center gap-3">
                  <Avatar className="size-12">
                    <AvatarFallback>AP</AvatarFallback>
                  </Avatar>
                  <div>
                    <p className="font-medium">Shared workspace</p>
                    <p className="text-xs text-muted-foreground">
                      Open instance · no sign-in
                    </p>
                  </div>
                </div>
                <Row label="Workspace ID">{user?.email ?? "…"}</Row>
                <Row label="Access">
                  <Badge variant="secondary">Open — no authentication</Badge>
                </Row>
              </CardContent>
            </Card>
          )}

          {section === "appearance" && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Appearance</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="mb-3 text-sm text-muted-foreground">
                  Choose your preferred theme. The choice is saved to the
                  workspace, so any browser opening this instance restores it.
                </p>
                <div className="grid grid-cols-3 gap-2">
                  {THEMES.map((option) => (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() => {
                        setTheme(option.value);
                        savePreferences.mutate({
                          theme: option.value as "light" | "dark" | "system",
                        });
                      }}
                      className={cn(
                        "rounded-lg border px-4 py-3 text-sm font-medium transition-colors",
                        mounted && theme === option.value
                          ? "border-primary bg-primary/5 text-primary"
                          : "hover:bg-accent",
                      )}
                    >
                      {option.label}
                    </button>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {section === "workspace" && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Workspace defaults</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="mb-3 text-sm text-muted-foreground">
                  Applied whenever a request does not specify its own value.
                  Saved for the whole instance.
                </p>
                <Row label="Retrieved passages (top-k)">
                  <input
                    type="number"
                    min={1}
                    max={20}
                    aria-label="Default number of retrieved passages"
                    value={preferences.data?.default_top_k ?? 5}
                    onChange={(event) =>
                      savePreferences.mutate({
                        default_top_k: Number(event.target.value),
                      })
                    }
                    className="h-8 w-20 rounded-md border bg-background px-2 text-sm"
                  />
                </Row>
                <Row label="Require approval by default">
                  <input
                    type="checkbox"
                    aria-label="Require approval by default"
                    checked={
                      preferences.data?.require_approval_by_default ?? false
                    }
                    onChange={(event) =>
                      savePreferences.mutate({
                        require_approval_by_default: event.target.checked,
                      })
                    }
                    className="size-4 accent-primary"
                  />
                </Row>
                <Row label="In-app notifications">
                  <input
                    type="checkbox"
                    aria-label="Enable in-app notifications"
                    checked={preferences.data?.notifications_enabled ?? true}
                    onChange={(event) =>
                      savePreferences.mutate({
                        notifications_enabled: event.target.checked,
                      })
                    }
                    className="size-4 accent-primary"
                  />
                </Row>
                {savePreferences.isError && (
                  <p role="alert" className="mt-3 text-sm text-destructive">
                    Could not save that change.
                  </p>
                )}
              </CardContent>
            </Card>
          )}

          {section === "models" && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">AI Models</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="mb-2 text-sm text-muted-foreground">
                  Models currently powering the platform (served locally via
                  Ollama).
                </p>
                <Row label="Language model">
                  <Badge variant="secondary">llama3.2</Badge>
                </Row>
                <Row label="Embedding model">
                  <Badge variant="secondary">nomic-embed-text</Badge>
                </Row>
                <Row label="Vector store">
                  <Badge variant="outline">ChromaDB</Badge>
                </Row>
              </CardContent>
            </Card>
          )}

          {section === "system" && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">System</CardTitle>
              </CardHeader>
              <CardContent>
                <Row label="Backend API">
                  <code className="rounded bg-muted px-1.5 py-0.5 text-xs">
                    {API_URL}
                  </code>
                </Row>
                <Row label="Connection">
                  {health.isError ? (
                    <Badge variant="destructive">Offline</Badge>
                  ) : health.isLoading ? (
                    <Badge variant="warning">Connecting…</Badge>
                  ) : (
                    <Badge variant="success">Operational</Badge>
                  )}
                </Row>
                <Row label="Database">
                  <Badge variant="outline">SQLite</Badge>
                </Row>
                <Row label="Vector store">
                  <Badge variant="outline">ChromaDB</Badge>
                </Row>
              </CardContent>
            </Card>
          )}

          {section === "about" && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">About</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-sm text-muted-foreground">
                <p>
                  <span className="font-medium text-foreground">
                    AutoPilot AI
                  </span>{" "}
                  — an enterprise multi-agent business automation platform.
                </p>
                <p>
                  Built with LangGraph, FastAPI, ChromaDB, Ollama, and Next.js.
                  Retrieval-augmented answers, human-in-the-loop approvals, and
                  a full execution audit trail.
                </p>
                <Row label="Version">v0.1.0</Row>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
