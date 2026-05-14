"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { InsightsPanel } from "@/components/InsightsPanel";
import { MobileHeader, Sidebar } from "@/components/Sidebar";
import { Loader2, Send, Upload } from "lucide-react";

const EXAMPLES = [
  {
    label: "Exit load — Mid Cap",
    query: "What is the exit load for HDFC Mid Cap Fund?",
  },
  {
    label: "Riskometer — Large Cap",
    query: "What is the riskometer rating for HDFC Large Cap Fund?",
  },
  {
    label: "Minimum SIP — ELSS",
    query: "What is the minimum SIP amount for HDFC ELSS Tax Saver Fund?",
  },
] as const;

const MAX_LEN = 500;
const TIMEOUT_MS = 120_000;

function newId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

type Msg = { id: string; role: "user" | "assistant"; text: string };

type BackendStatus = "checking" | "ok" | "error";

export function ChatShell() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [showWelcome, setShowWelcome] = useState(true);
  const [menuOpen, setMenuOpen] = useState(false);
  const [backendStatus, setBackendStatus] = useState<BackendStatus>("checking");
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const res = await fetch("/api/health", { cache: "no-store" });
        const data = (await res.json()) as { status?: string };
        const ok = res.ok && data.status === "ok";
        if (!cancelled) setBackendStatus(ok ? "ok" : "error");
      } catch {
        if (!cancelled) setBackendStatus("error");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const scrollToBottom = () => {
    requestAnimationFrame(() => {
      listRef.current?.scrollTo({
        top: listRef.current.scrollHeight,
        behavior: "smooth",
      });
    });
  };

  const send = useCallback(
    async (raw: string) => {
      const text = raw.trim().replace(/\s+/g, " ");
      if (!text || loading) return;

      setShowWelcome(false);
      const userMsg: Msg = {
        id: newId(),
        role: "user",
        text: text.slice(0, MAX_LEN),
      };
      setMessages((m) => [...m, userMsg]);
      setInput("");
      setLoading(true);
      scrollToBottom();

      const controller = new AbortController();
      const tid = window.setTimeout(() => controller.abort(), TIMEOUT_MS);

      try {
        const res = await fetch("/api/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: userMsg.text }),
          signal: controller.signal,
        });
        const raw = await res.text();
        let reply = "";

        if (res.status === 503) {
          reply =
            "The assistant is temporarily unavailable. Please try again in a moment.";
        } else if (res.ok) {
          try {
            reply = (JSON.parse(raw) as { reply?: string }).reply ?? "";
          } catch {
            reply = raw;
          }
        } else {
          try {
            const j = JSON.parse(raw) as { reply?: string };
            reply =
              j.reply?.trim() ||
              `Something went wrong (${res.status}).`;
          } catch {
            reply = `Something went wrong (${res.status}).`;
          }
        }

        if (!reply.trim()) reply = "(Empty response)";
        setMessages((m) => [
          ...m,
          { id: newId(), role: "assistant", text: reply },
        ]);
      } catch (e) {
        const msg =
          (e as Error).name === "AbortError"
            ? "That took too long. Please try again."
            : "Network error. Start the FastAPI server on port 8000, then refresh.";
        setMessages((m) => [
          ...m,
          { id: newId(), role: "assistant", text: msg },
        ]);
      } finally {
        window.clearTimeout(tid);
        setLoading(false);
        scrollToBottom();
      }
    },
    [loading],
  );

  const newChat = () => {
    setMessages([]);
    setShowWelcome(true);
    setInput("");
  };

  return (
    <div className="flex h-screen bg-background text-on-background">
      <Sidebar
        onNewChat={newChat}
        mobileOpen={menuOpen}
        onCloseMobile={() => setMenuOpen(false)}
      />

      <main className="flex flex-1 flex-col md:ml-[280px]">
        <MobileHeader onOpenMenu={() => setMenuOpen(true)} />

        <div className="flex min-h-0 flex-1 overflow-hidden">
          <div className="mx-auto flex w-full max-w-chat flex-1 flex-col">
            <div
              ref={listRef}
              className="hide-scrollbar flex-1 space-y-6 overflow-y-auto px-4 py-6 md:px-8"
            >
              {showWelcome ? (
                <section className="space-y-4 rounded-xl border border-surface-container-high bg-surface-container-low/60 p-5 shadow-card">
                  <h2 className="font-display text-lg font-semibold text-on-surface md:text-2xl">
                    Welcome to HDFC Mutual Fund FAQ
                  </h2>
                  <p className="text-sm leading-relaxed text-on-surface-variant md:text-base">
                    Ask factual questions about the five supported HDFC schemes.
                    Tap an example or type below — responses stay within the
                    curated corpus.
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {EXAMPLES.map((ex) => (
                      <button
                        key={ex.label}
                        type="button"
                        disabled={loading}
                        onClick={() => void send(ex.query)}
                        className="rounded-full border border-outline-variant/50 bg-surface-container px-4 py-2 text-left text-xs font-medium text-primary transition-colors hover:border-primary/50 hover:bg-surface-container-high disabled:opacity-50 md:text-sm"
                      >
                        {ex.label}
                      </button>
                    ))}
                  </div>
                </section>
              ) : null}

              {messages.map((m) => (
                <div
                  key={m.id}
                  className={
                    m.role === "user" ? "flex justify-end" : "flex justify-start"
                  }
                >
                  <div
                    className={
                      m.role === "user"
                        ? "max-w-[85%] rounded-xl rounded-tr-sm border border-primary/25 bg-surface-container-highest px-4 py-3 text-sm shadow-card md:text-base"
                        : "relative max-w-[90%] rounded-xl rounded-tl-sm border border-surface-container-high bg-surface-container-low px-5 py-4 text-sm shadow-card md:text-base"
                    }
                  >
                    {m.role === "assistant" ? (
                      <span className="absolute -left-1.5 -top-1.5 h-3 w-3 rounded-full border-2 border-background bg-primary shadow-[0_0_10px_rgba(68,237,183,0.45)]" />
                    ) : null}
                    <p className="whitespace-pre-wrap break-words text-on-surface">
                      {m.text}
                    </p>
                  </div>
                </div>
              ))}

              {loading ? (
                <div className="flex items-center gap-3 text-on-surface-variant">
                  <span className="relative flex h-3 w-3">
                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-40" />
                    <span className="relative inline-flex h-3 w-3 rounded-full bg-primary" />
                  </span>
                  <Loader2 className="h-4 w-4 animate-spin text-primary" />
                  <span className="font-mono text-xs tracking-tight">
                    Retrieving & drafting answer…
                  </span>
                </div>
              ) : null}
            </div>

            <div className="border-t border-surface-container-high bg-gradient-to-t from-background via-background to-transparent px-4 pb-4 pt-2 md:px-8">
              <form
                className="relative flex items-center gap-1 rounded-full border border-surface-container-high bg-surface-container-low p-1.5 shadow-input"
                onSubmit={(e) => {
                  e.preventDefault();
                  void send(input);
                }}
              >
                <button
                  type="button"
                  className="rounded-full p-2.5 text-secondary hover:bg-surface-container hover:text-primary"
                  aria-label="Attach (not available)"
                  disabled
                >
                  <Upload className="h-5 w-5 opacity-40" />
                </button>
                <textarea
                  rows={1}
                  maxLength={MAX_LEN}
                  disabled={loading}
                  placeholder="Ask a factual question about an HDFC scheme…"
                  className="max-h-32 min-h-[44px] flex-1 resize-none bg-transparent px-3 py-2.5 text-sm text-on-surface placeholder:text-secondary focus:outline-none md:text-base"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      void send(input);
                    }
                  }}
                />
                <button
                  type="submit"
                  disabled={loading || !input.trim()}
                  className="rounded-full bg-primary p-3 text-on-primary shadow-glow transition hover:bg-primary-container disabled:cursor-not-allowed disabled:opacity-40"
                  aria-label="Send"
                >
                  <Send className="h-5 w-5" />
                </button>
              </form>
              <p className="mt-2 text-center text-[10px] font-semibold uppercase tracking-wide text-secondary">
                {backendStatus === "checking" ? (
                  <>Checking API… · </>
                ) : backendStatus === "ok" ? (
                  <>API connected · </>
                ) : (
                  <span className="text-amber-400/90">
                    API offline — run{" "}
                    <code className="rounded bg-surface-container px-1 py-0.5 font-mono normal-case">
                      uvicorn src.chat_app:app --host 127.0.0.1 --port 8000
                    </code>{" "}
                    ·{" "}
                  </span>
                )}
                AI can make mistakes · Verify critical data · {input.length} /{" "}
                {MAX_LEN}
              </p>
            </div>
          </div>

          <InsightsPanel />
        </div>
      </main>
    </div>
  );
}
