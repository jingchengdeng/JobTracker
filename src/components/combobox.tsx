"use client";
import { useState, useEffect } from "react";
import { ChevronsUpDown } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";

interface ComboboxProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  field: string;
}

export function Combobox({
  value,
  onChange,
  placeholder = "Select...",
  field,
}: ComboboxProps) {
  const [open, setOpen] = useState(false);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [inputValue, setInputValue] = useState("");

  useEffect(() => {
    fetch(`/api/jobs/suggestions?field=${field}`)
      .then((r) => r.json())
      .then((data) => {
        if (Array.isArray(data)) setSuggestions(data);
      })
      .catch(() => {});
  }, [field]);

  const filtered = suggestions.filter((s) =>
    s.toLowerCase().includes(inputValue.toLowerCase())
  );

  return (
    <Popover
      open={open}
      onOpenChange={(isOpen) => setOpen(isOpen)}
    >
      <PopoverTrigger
        aria-expanded={open}
        className={cn(
          "inline-flex w-full items-center justify-between rounded-lg border border-input bg-background px-2.5 py-2 text-sm font-normal whitespace-nowrap transition-colors outline-none hover:bg-muted hover:text-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:pointer-events-none disabled:opacity-50 dark:border-input dark:bg-input/30 dark:hover:bg-input/50"
        )}
      >
        <span className={cn(!value && "text-muted-foreground")}>
          {value || placeholder}
        </span>
        <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
      </PopoverTrigger>
      <PopoverContent
        className="p-0"
        align="start"
        style={{ width: "var(--anchor-width)" } as React.CSSProperties}
      >
        <Command>
          <CommandInput
            placeholder="Search or type new..."
            value={inputValue}
            onValueChange={setInputValue}
          />
          <CommandList>
            <CommandEmpty>
              {inputValue ? (
                <button
                  className="w-full px-2 py-1.5 text-sm text-left hover:bg-accent"
                  onClick={() => {
                    onChange(inputValue);
                    setOpen(false);
                    setInputValue("");
                  }}
                >
                  Use &quot;{inputValue}&quot;
                </button>
              ) : (
                "No results."
              )}
            </CommandEmpty>
            <CommandGroup>
              {filtered.map((item) => (
                <CommandItem
                  key={item}
                  value={item}
                  data-checked={value === item ? "true" : undefined}
                  onSelect={() => {
                    onChange(item);
                    setOpen(false);
                    setInputValue("");
                  }}
                >
                  {item}
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
