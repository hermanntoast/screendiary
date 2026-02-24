import { useMemo } from "react";
import { marked } from "marked";
import type { ChatMessage as ChatMsg } from "../../api/client";

// Configure marked for safe inline rendering
marked.setOptions({
  breaks: true,
  gfm: true,
});

interface Props {
  message: ChatMsg;
  streaming?: boolean;
}

export function ChatMessage({ message, streaming }: Props) {
  const isUser = message.role === "user";

  const html = useMemo(() => {
    if (isUser || !message.content) return "";
    return marked.parse(message.content) as string;
  }, [isUser, message.content]);

  return (
    <div className={`chat-msg ${isUser ? "chat-msg-user" : "chat-msg-assistant"}`}>
      <div className={`chat-bubble ${isUser ? "chat-bubble-user" : "chat-bubble-assistant"}`}>
        {isUser ? (
          message.content
        ) : message.content ? (
          <div className="chat-md" dangerouslySetInnerHTML={{ __html: html }} />
        ) : streaming ? (
          <span className="chat-cursor" />
        ) : null}
      </div>
    </div>
  );
}
