import {
  BarChart3,
  BookOpen,
  Bot,
  ClipboardCheck,
  FileText,
  LayoutDashboard,
  ListTodo,
  Mail,
  type LucideIcon,
  Settings,
  Sparkles,
  Workflow,
  Wrench,
} from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  /** Optional key into a live badge-count map (e.g. pending approvals). */
  badgeKey?: "approvals";
  /** Placeholder for a feature delivered in a later milestone. */
  disabled?: boolean;
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

/** Grouped navigation, shared by the sidebar and the command palette. */
export const navGroups: NavGroup[] = [
  {
    label: "Overview",
    items: [
      { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
      { href: "/assistant", label: "Assistant", icon: Sparkles },
    ],
  },
  {
    label: "Workspace",
    items: [
      { href: "/emails", label: "Email", icon: Mail },
      { href: "/documents", label: "Documents", icon: FileText },
      { href: "/knowledge", label: "Knowledge", icon: BookOpen },
      { href: "/agents", label: "Agents", icon: Bot },
      { href: "/tasks", label: "Tasks", icon: ListTodo },
      { href: "/workflows", label: "Workflows", icon: Workflow },
      { href: "/tools", label: "Tools", icon: Wrench },
      {
        href: "/approvals",
        label: "Approvals",
        icon: ClipboardCheck,
        badgeKey: "approvals",
      },
    ],
  },
  {
    label: "Insights",
    items: [{ href: "/analytics", label: "Analytics", icon: BarChart3 }],
  },
];

/** The single item pinned to the bottom of the sidebar. */
export const settingsNavItem: NavItem = {
  href: "/settings",
  label: "Settings",
  icon: Settings,
};

/** Flat list of every navigable item (used by the command palette). */
export const navItems: NavItem[] = [
  ...navGroups.flatMap((group) => group.items),
  settingsNavItem,
];
