import { useState } from "react";
import { Link } from "react-router-dom";
import { Plus, MessageSquare, X, Pencil, Trash2, Check, Settings, Bell } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useLanguage } from "@/contexts/LanguageContext";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

function cn(...inputs) {
  return twMerge(clsx(inputs));
}

const COPY = {
  en: {
    newChat: "New Chat",
    deleteConfirm: "Are you sure you want to delete this chat?",
    rename: "Rename",
    delete: "Delete",
    noChats: "No previous chats.",
    alerts: "Alerts",
    settings: "Settings",
  },
  am: {
    newChat: "አዲስ ውይይት",
    deleteConfirm: "ይህን ውይይት ማጥፋት ይፈልጋሉ?",
    rename: "ስም ቀይር",
    delete: "አጥፋ",
    noChats: "ቀደም ያሉ ውይይቶች የሉም።",
    alerts: "አስጠንቅቂያዎች",
    settings: "ቅንብሮች",
  },
};

export function ChatSidebar({
  sessions,
  activeSessionId,
  onSelectSession,
  onNewSession,
  onRenameSession,
  onDeleteSession,
  isOpen,
  setIsOpen,
}) {
  const { language } = useLanguage();
  const copy = COPY[language] || COPY.en;
  const [editingId, setEditingId] = useState(null);
  const [editTitle, setEditTitle] = useState("");

  const startEditing = (e, session) => {
    e.stopPropagation();
    setEditingId(session.session_id);
    setEditTitle(session.title || copy.newChat);
  };

  const saveEdit = (e, sessionId) => {
    e.stopPropagation();
    if (editTitle.trim()) {
      onRenameSession?.(sessionId, editTitle.trim());
    }
    setEditingId(null);
  };

  const cancelEdit = (e) => {
    e.stopPropagation();
    setEditingId(null);
  };

  const handleDelete = (e, sessionId) => {
    e.stopPropagation();
    if (confirm(copy.deleteConfirm)) {
      onDeleteSession?.(sessionId);
    }
  };

  return (
    <>
      {/* Mobile Backdrop */}
      {isOpen && (
        <div 
          className="fixed inset-0 z-40 bg-black/50 md:hidden" 
          onClick={() => setIsOpen(false)}
        />
      )}
      
      {/* Sidebar */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 w-72 flex-col border-r border-border bg-card transition-transform duration-300 md:static md:flex md:w-64 md:translate-x-0",
          isOpen ? "translate-x-0 flex" : "-translate-x-full hidden md:flex"
        )}
      >
        <div className="flex items-center justify-between p-4 border-b border-border">
          <Button onClick={onNewSession} className="w-full justify-start gap-2">
            <Plus className="h-4 w-4" />
            {copy.newChat}
          </Button>
          <Button 
            variant="ghost" 
            size="icon" 
            className="md:hidden ml-2" 
            onClick={() => setIsOpen(false)}
          >
            <X className="h-5 w-5" />
          </Button>
        </div>

        <div className="flex-1 overflow-y-auto p-3">
          <div className="flex flex-col gap-2">
            {sessions.map((session) => {
              const isActive = activeSessionId === session.session_id;
              const isEditing = editingId === session.session_id;

              return (
                <div
                  key={session.session_id}
                  onClick={() => {
                    if (!isEditing) {
                      onSelectSession(session.session_id);
                      setIsOpen(false);
                    }
                  }}
                  className={cn(
                    "group relative flex min-h-11 items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors cursor-pointer",
                    isActive
                      ? "bg-secondary text-secondary-foreground font-medium"
                      : "text-muted-foreground hover:bg-muted hover:text-foreground"
                  )}
                >
                  <MessageSquare className="h-4 w-4 shrink-0" />
                  
                  {isEditing ? (
                    <div className="flex flex-1 items-center gap-1 overflow-hidden">
                      <input
                        autoFocus
                        value={editTitle}
                        onChange={(e) => setEditTitle(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") saveEdit(e, session.session_id);
                          if (e.key === "Escape") cancelEdit(e);
                        }}
                        className="flex-1 min-w-0 bg-background text-foreground px-1 py-0.5 text-xs rounded border outline-none focus:ring-1 focus:ring-primary"
                        onClick={(e) => e.stopPropagation()}
                      />
                      <button onClick={(e) => saveEdit(e, session.session_id)} className="inline-flex h-8 w-8 items-center justify-center rounded-md hover:bg-muted hover:text-primary">
                        <Check className="h-3 w-3" />
                      </button>
                      <button onClick={cancelEdit} className="inline-flex h-8 w-8 items-center justify-center rounded-md hover:bg-muted hover:text-destructive">
                        <X className="h-3 w-3" />
                      </button>
                    </div>
                  ) : (
                    <>
                      <span className="truncate flex-1 text-left">
                        {session.title || copy.newChat}
                      </span>
                      
                      <div className={cn(
                        "flex items-center gap-1 opacity-100 transition-opacity md:opacity-0 md:group-hover:opacity-100",
                        isActive && "md:opacity-100"
                      )}>
                        <button 
                          onClick={(e) => startEditing(e, session)}
                          className="inline-flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-primary"
                          title={copy.rename}
                          aria-label={copy.rename}
                        >
                          <Pencil className="h-3.5 w-3.5" />
                        </button>
                        <button 
                          onClick={(e) => handleDelete(e, session.session_id)}
                          className="inline-flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-destructive"
                          title={copy.delete}
                          aria-label={copy.delete}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </>
                  )}
                </div>
              );
            })}
            
            {sessions.length === 0 && (
              <p className="text-xs text-center text-muted-foreground mt-4">
                {copy.noChats}
              </p>
            )}
          </div>
        </div>

        <div className="border-t border-border p-3">
          <div className="grid gap-1">
            <Link
              to="/alerts"
              onClick={() => setIsOpen(false)}
              className="flex min-h-11 items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              <Bell className="h-4 w-4" />
              {copy.alerts}
            </Link>
            <Link
              to="/settings"
              onClick={() => setIsOpen(false)}
              className="flex min-h-11 items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              <Settings className="h-4 w-4" />
              {copy.settings}
            </Link>
          </div>
        </div>
      </aside>
    </>
  );
}
