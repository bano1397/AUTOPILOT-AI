"use client";

import { Moon, Plus, Sun, Upload } from "lucide-react";
import { useTheme } from "next-themes";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
  CommandShortcut,
} from "@/components/ui/command";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { useCommandPalette } from "@/lib/command/store";
import { navItems } from "@/components/layout/nav-items";

/**
 * Global ⌘K palette: fuzzy navigation, quick actions, and theme switching.
 * Mounted once in the dashboard layout; opens via ⌘K/Ctrl-K or the search bar.
 */
export function CommandPalette() {
  const { open, setOpen, toggle } = useCommandPalette();
  const router = useRouter();
  const { setTheme } = useTheme();

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "k" && (event.metaKey || event.ctrlKey)) {
        event.preventDefault();
        toggle();
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [toggle]);

  function run(action: () => void) {
    setOpen(false);
    action();
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent hideClose className="max-w-xl gap-0 overflow-hidden p-0">
        <DialogTitle className="sr-only">Command palette</DialogTitle>
        <Command loop>
          <CommandInput placeholder="Search pages, run a command…" />
          <CommandList>
            <CommandEmpty>No results found.</CommandEmpty>

            <CommandGroup heading="Navigation">
              {navItems.map((item) => {
                const Icon = item.icon;
                return (
                  <CommandItem
                    key={item.href}
                    value={`go ${item.label}`}
                    onSelect={() => run(() => router.push(item.href))}
                  >
                    <Icon />
                    <span>{item.label}</span>
                  </CommandItem>
                );
              })}
            </CommandGroup>

            <CommandSeparator />

            <CommandGroup heading="Actions">
              <CommandItem
                value="new chat ask assistant"
                onSelect={() => run(() => router.push("/assistant"))}
              >
                <Plus />
                <span>New assistant chat</span>
                <CommandShortcut>⌘J</CommandShortcut>
              </CommandItem>
              <CommandItem
                value="upload document"
                onSelect={() => run(() => router.push("/documents"))}
              >
                <Upload />
                <span>Upload a document</span>
              </CommandItem>
            </CommandGroup>

            <CommandSeparator />

            <CommandGroup heading="Theme">
              <CommandItem
                value="light theme"
                onSelect={() => run(() => setTheme("light"))}
              >
                <Sun />
                <span>Light mode</span>
              </CommandItem>
              <CommandItem
                value="dark theme"
                onSelect={() => run(() => setTheme("dark"))}
              >
                <Moon />
                <span>Dark mode</span>
              </CommandItem>
            </CommandGroup>
          </CommandList>
        </Command>
      </DialogContent>
    </Dialog>
  );
}
