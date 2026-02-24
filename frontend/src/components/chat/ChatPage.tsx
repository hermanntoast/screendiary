import { useRef, useEffect, useCallback, type KeyboardEvent } from "react";
import { useChatStore } from "../../chatStore";
import { ChatMessage } from "./ChatMessage";

export function ChatPage() {
  const messages = useChatStore((s) => s.messages);
  const input = useChatStore((s) => s.input);
  const streaming = useChatStore((s) => s.streaming);
  const setInput = useChatStore((s) => s.setInput);
  const sendMessage = useChatStore((s) => s.sendMessage);
  const clearChat = useChatStore((s) => s.clearChat);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const hasMessages = messages.length > 0;

  // Auto-scroll on new content
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Auto-resize textarea
  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = Math.min(ta.scrollHeight, 200) + "px";
  }, [input]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    },
    [sendMessage],
  );

  return (
    <div className="chat-page">
      {hasMessages ? (
        <>
          <div className="chat-messages">
            {messages.map((msg, i) => (
              <ChatMessage
                key={i}
                message={msg}
                streaming={streaming && i === messages.length - 1 && msg.role === "assistant"}
              />
            ))}
            <div ref={messagesEndRef} />
          </div>
          <div className="chat-input-bar">
            <div className="chat-input-row">
              <textarea
                ref={textareaRef}
                className="chat-input"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Nachricht eingeben..."
                rows={1}
                disabled={streaming}
              />
              <button
                className="chat-send-btn"
                onClick={sendMessage}
                disabled={streaming || !input.trim()}
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M22 2 11 13" /><path d="m22 2-7 20-4-9-9-4z" />
                </svg>
              </button>
            </div>
            <button className="chat-clear-btn" onClick={clearChat}>
              Neuer Chat
            </button>
          </div>
        </>
      ) : (
        <div className="chat-empty">
          <div className="chat-empty-center">
            <img src="/favicon.png" alt="ScreenDiary" className="chat-logo" />
            <h1 className="chat-title">ScreenDiary</h1>
            <p className="chat-tagline">Frag mich etwas ueber deine Bildschirmaktivitaeten</p>
          </div>
          <div className="chat-input-bar chat-input-bar-empty">
            <div className="chat-input-row">
              <textarea
                ref={textareaRef}
                className="chat-input"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Nachricht eingeben..."
                rows={1}
              />
              <button
                className="chat-send-btn"
                onClick={sendMessage}
                disabled={!input.trim()}
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M22 2 11 13" /><path d="m22 2-7 20-4-9-9-4z" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
