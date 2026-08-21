import { useState, useCallback, useEffect } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { getWriteKey, setWriteKey, hasWriteKey } from "@/lib/queryClient";

// Custom event dispatched by apiRequest when a mutation gets 401
export const WRITE_KEY_REQUIRED_EVENT = "write-key-required";

/**
 * WriteKeyGate — listens for the "write-key-required" custom event
 * (dispatched by apiRequest when a mutation returns 401) and prompts
 * the user to enter the write key. Once entered, the key is stored in
 * browser storage and all subsequent mutations include it automatically.
 *
 * Also exposes a global helper so non-apiRequest fetch calls can trigger
 * the prompt by dispatching the event manually.
 */
export function WriteKeyGate() {
  const [open, setOpen] = useState(false);
  const [keyInput, setKeyInput] = useState("");
  const [error, setError] = useState("");

  // Listen for write-key-required events from anywhere in the app
  useEffect(() => {
    const handler = () => {
      // Only open if we don't already have a key (or if the key was cleared)
      if (!hasWriteKey()) {
        setOpen(true);
      }
    };
    window.addEventListener(WRITE_KEY_REQUIRED_EVENT, handler);
    return () => window.removeEventListener(WRITE_KEY_REQUIRED_EVENT, handler);
  }, []);

  // Also listen for 401 responses globally via window.fetch interception
  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      if (detail?.status === 401) {
        if (!hasWriteKey()) {
          setOpen(true);
        }
      }
    };
    window.addEventListener("fetch-error", handler as EventListener);
    return () => window.removeEventListener("fetch-error", handler as EventListener);
  }, []);

  const handleSave = useCallback(() => {
    const trimmed = keyInput.trim();
    if (!trimmed) {
      setError("Please enter a write key");
      return;
    }
    setWriteKey(trimmed);
    setKeyInput("");
    setError("");
    setOpen(false);
    // Dispatch event so callers can retry their mutation
    window.dispatchEvent(new CustomEvent("write-key-updated"));
  }, [keyInput]);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Write Access Required</DialogTitle>
          <DialogDescription>
            Enter your write key to save changes, add leads, log revenue, and perform other actions.
            Contact your administrator if you don't have the key.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2 py-4">
          <Input
            type="password"
            placeholder="Enter write key"
            value={keyInput}
            onChange={(e) => {
              setKeyInput(e.target.value);
              setError("");
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleSave();
            }}
            autoFocus
          />
          {error && <p className="text-sm text-red-500">{error}</p>}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button onClick={handleSave}>
            Save Key
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
