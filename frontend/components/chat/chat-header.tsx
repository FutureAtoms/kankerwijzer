"use client";

import { PanelLeftIcon } from "lucide-react";
import Link from "next/link";
import { memo } from "react";
import { Button } from "@/components/ui/button";
import { useSidebar } from "@/components/ui/sidebar";
import { VisibilitySelector, type VisibilityType } from "./visibility-selector";

function PureChatHeader({
  chatId,
  selectedVisibilityType,
  isReadonly,
}: {
  chatId: string;
  selectedVisibilityType: VisibilityType;
  isReadonly: boolean;
}) {
  const { state, toggleSidebar, isMobile } = useSidebar();

  if (state === "collapsed" && !isMobile) {
    return null;
  }

  return (
    <header className="sticky top-0 flex h-14 items-center gap-2 bg-sidebar px-3">
      <Button
        className="md:hidden"
        onClick={toggleSidebar}
        size="icon-sm"
        variant="ghost"
      >
        <PanelLeftIcon className="size-4" />
      </Button>

      <Link
        className="flex items-center gap-2 rounded-lg px-2 py-1 md:hidden"
        href="/"
      >
        <svg
          width="20"
          height="20"
          viewBox="0 0 32 32"
          fill="none"
          className="text-primary"
        >
          <circle
            cx="16"
            cy="16"
            r="15"
            stroke="currentColor"
            strokeWidth="2"
          />
          <path
            d="M16 8v10M12 14l4 4 4-4"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <circle cx="16" cy="22" r="1.5" fill="currentColor" />
        </svg>
        <span className="text-sm font-semibold text-foreground">
          KankerWijzer
        </span>
      </Link>

      {!isReadonly && (
        <VisibilitySelector
          chatId={chatId}
          selectedVisibilityType={selectedVisibilityType}
        />
      )}

      <div className="hidden items-center gap-2 md:ml-auto md:flex">
        <span className="text-xs text-muted-foreground">
          Betrouwbare kankerinformatie van IKNL
        </span>
      </div>
    </header>
  );
}

export const ChatHeader = memo(PureChatHeader, (prevProps, nextProps) => {
  return (
    prevProps.chatId === nextProps.chatId &&
    prevProps.selectedVisibilityType === nextProps.selectedVisibilityType &&
    prevProps.isReadonly === nextProps.isReadonly
  );
});
