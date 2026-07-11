"use client";

import {
  Cpu,
  Info,
  type LucideIcon,
  Palette,
  Server,
  User as UserIcon,
} from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useHealth } from "@/features/system/hooks";
import { useAuthStore } from "@/lib/auth/store";
import { API_URL } from "@/lib/config";
import { cn } from "@/lib/utils";

type Section = "profile" | "appearance" | "models" | "system" | "about";

const NAV: { key: Section; label: string; icon: LucideIcon }[] = [
  { key: "profile", label: "Profile", icon: UserIcon },
  { key: "appearance", label: "Appearance", icon: Palette },
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
  const user = useAuthStore((state) => state.user);
  const { theme, setTheme } = useTheme();
  const health = useHealth();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="text-muted-foreground">
          Manage your account, appearance, and platform configuration.
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
                    <AvatarFallback>
                      {user?.email?.[0]?.toUpperCase() ?? "?"}
                    </AvatarFallback>
                  </Avatar>
                  <div>
                    <p className="font-medium">{user?.email ?? "…"}</p>
                    <p className="text-xs text-muted-foreground">
                      AutoPilot AI account
                    </p>
                  </div>
                </div>
                <Row label="Email">{user?.email ?? "…"}</Row>
                <Row label="Role">
                  {user?.role ? (
                    <Badge
                      variant={user.role === "admin" ? "default" : "secondary"}
                    >
                      {user.role}
                    </Badge>
                  ) : (
                    "…"
                  )}
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
                  Choose your preferred theme.
                </p>
                <div className="grid grid-cols-3 gap-2">
                  {THEMES.map((option) => (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() => setTheme(option.value)}
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
