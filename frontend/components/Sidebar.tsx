import {
  HelpCircle,
  History,
  Layers,
  Menu,
  MessageSquarePlus,
  Sparkles,
} from "lucide-react";

type SidebarProps = {
  onNewChat: () => void;
  mobileOpen: boolean;
  onCloseMobile: () => void;
};

export function Sidebar({
  onNewChat,
  mobileOpen,
  onCloseMobile,
}: SidebarProps) {
  return (
    <>
      {/* Mobile overlay */}
      {mobileOpen ? (
        <button
          type="button"
          aria-label="Close menu"
          className="fixed inset-0 z-40 bg-black/60 md:hidden"
          onClick={onCloseMobile}
        />
      ) : null}

      <nav
        className={`fixed left-0 top-0 z-50 flex h-full w-[280px] flex-col border-r border-surface-container-high bg-surface-container-lowest p-4 transition-transform duration-200 md:translate-x-0 ${
          mobileOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"
        }`}
      >
        <div className="mb-8 flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-primary font-display text-sm font-bold text-on-primary">
            G
          </div>
          <div>
            <h1 className="font-display text-xl font-bold leading-8 text-primary">
              Groww AI
            </h1>
            <p className="text-xs text-secondary">HDFC FAQ · Facts-only</p>
          </div>
        </div>

        <div className="hide-scrollbar flex-1 space-y-1 overflow-y-auto">
          <button
            type="button"
            onClick={() => {
              onNewChat();
              onCloseMobile();
            }}
            className="flex w-full items-center gap-3 rounded-lg p-3 text-left text-secondary transition-colors hover:bg-surface-container hover:text-primary"
          >
            <MessageSquarePlus className="h-5 w-5 shrink-0" />
            <span className="text-sm">New chat</span>
          </button>
          <div className="flex items-center gap-3 rounded-lg border-r-4 border-primary bg-surface-container p-3 text-primary">
            <History className="h-5 w-5 shrink-0" />
            <span className="text-sm font-semibold">HDFC schemes</span>
          </div>
          <div className="flex items-center gap-3 rounded-lg p-3 text-secondary">
            <Layers className="h-5 w-5 shrink-0" />
            <span className="text-sm">5 Groww-sourced funds</span>
          </div>
          <div className="flex items-center gap-3 rounded-lg p-3 text-secondary">
            <Sparkles className="h-5 w-5 shrink-0" />
            <span className="text-sm">RAG + Groq</span>
          </div>
        </div>

        <div className="mt-auto space-y-2 border-t border-surface-container-high pt-4">
          <p className="rounded-lg border border-outline-variant/40 bg-surface-container/80 p-3 text-xs leading-relaxed text-on-surface-variant">
            Facts-only. No investment advice.
          </p>
          <button
            type="button"
            className="flex w-full items-center gap-3 rounded-lg p-3 text-secondary transition-colors hover:bg-surface-container hover:text-primary"
          >
            <HelpCircle className="h-5 w-5 shrink-0" />
            <span className="text-sm">Help</span>
          </button>
        </div>
      </nav>
    </>
  );
}

export function MobileHeader({ onOpenMenu }: { onOpenMenu: () => void }) {
  return (
    <header className="sticky top-0 z-30 flex h-14 w-full items-center justify-between border-b border-surface-container-high bg-background/90 px-4 backdrop-blur-md md:hidden">
      <span className="font-display text-lg font-bold text-primary">
        Groww AI
      </span>
      <button
        type="button"
        aria-label="Open menu"
        className="rounded-lg p-2 text-secondary hover:bg-surface-container hover:text-primary"
        onClick={onOpenMenu}
      >
        <Menu className="h-6 w-6" />
      </button>
    </header>
  );
}
