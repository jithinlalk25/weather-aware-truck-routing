import { Command as CommandPrimitive } from "cmdk";
import { Loader2, MapPin } from "lucide-react";
import { useState } from "react";

import { usePlaceSearch } from "@/api/hooks";
import type { Place } from "@/api/types";
import { Command, CommandEmpty, CommandItem, CommandList } from "@/components/ui/command";
import { cn } from "@/lib/utils";

interface Props {
  label: string;
  value: Place | null;
  onChange: (place: Place | null) => void;
  placeholder?: string;
  error?: string;
}

export function PlaceAutocomplete({ label, value, onChange, placeholder, error }: Props) {
  const [text, setText] = useState<string | null>(null); // null = show the selected place
  const [open, setOpen] = useState(false);
  // A place set from outside (example chip, swap) replaces whatever was typed.
  const [shownValue, setShownValue] = useState(value);
  if (value !== shownValue) {
    setShownValue(value);
    if (value) setText(null);
  }
  const query = text ?? "";
  const search = usePlaceSearch(query);
  const results = search.data ?? [];
  const showList = open && query.trim().length >= 3;

  const choose = (p: Place) => {
    onChange(p);
    setText(null);
    setOpen(false);
  };

  return (
    <div className="grid gap-1.5">
      {/* cmdk renders its own screen-reader label (from `label`) wired to the input. */}
      <span aria-hidden className="text-xs font-medium text-muted-foreground">
        {label}
      </span>
      <Command
        label={label}
        shouldFilter={false}
        className="relative overflow-visible rounded-md bg-transparent p-0"
      >
        <div className="relative">
          <MapPin className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
          <CommandPrimitive.Input
            value={text ?? value?.label ?? ""}
            placeholder={placeholder}
            autoComplete="off"
            aria-invalid={!!error}
            onValueChange={(v) => {
              setText(v);
              setOpen(true);
              if (value) onChange(null);
            }}
            onFocus={() => setOpen(true)}
            onBlur={() => window.setTimeout(() => setOpen(false), 120)}
            onKeyDown={(e) => e.key === "Escape" && setOpen(false)}
            className={cn(
              "h-9 w-full rounded-md border border-input bg-transparent pr-8 pl-8 text-sm shadow-xs outline-none",
              "placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50",
              error && "border-destructive",
            )}
          />
          {search.isFetching && (
            <Loader2 className="absolute top-1/2 right-2.5 size-4 -translate-y-1/2 animate-spin text-muted-foreground" />
          )}
        </div>
        {showList && (
          <div className="absolute top-full z-50 mt-1 w-full rounded-md border bg-popover p-1 text-popover-foreground shadow-lg">
            <CommandList>
              {search.isError ? (
                <div className="px-2 py-3 text-sm text-destructive">
                  {(search.error as Error).message}
                </div>
              ) : (
                <CommandEmpty>{search.isFetching ? "Searching…" : "No US places found."}</CommandEmpty>
              )}
              {results.map((p) => (
                <CommandItem
                  key={`${p.label}|${p.lat}|${p.lon}`}
                  value={`${p.label}|${p.lat}|${p.lon}`}
                  onMouseDown={(e) => e.preventDefault()}
                  onSelect={() => choose(p)}
                >
                  <MapPin className="size-3.5 text-muted-foreground" />
                  {p.label}
                </CommandItem>
              ))}
            </CommandList>
          </div>
        )}
      </Command>
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  );
}
