import { useState, useEffect, useRef, useCallback } from "react";
import { useChat } from "../contexts/ChatContext";
export type ChatInputProps = {
  onSend: (message: string) => void;
  onAbort: () => void;
};

export function ChatInput({ onSend, onAbort }: ChatInputProps) {
  const { status } = useChat();
  const [message, setMessage] = useState("");
  const { isModelLoaded } = useChat();
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = useCallback(() => {
    const trimmedMessage = message.trim();

    if (trimmedMessage) {
      onSend(trimmedMessage);
      setMessage("");
    }
  }, [message, onSend]);

  const handleAbort = useCallback(() => {
    setMessage("");
    onAbort();
  }, [onAbort]);

  const handleSendOrAbort = useCallback(() => {
    if (status === "responding") {
      handleAbort();
    } else {
      handleSend();
    }
  }, [status, handleSend, handleAbort]);

  useEffect(() => {
    if (isModelLoaded && textareaRef.current) {
      textareaRef.current.focus();
    }
  }, [isModelLoaded]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      const trimmedMessage = message.trim();

      if (trimmedMessage) {
        onSend(trimmedMessage);
        setMessage("");
      }

      e.preventDefault();
      e.stopPropagation();
    }
  };

  const isResponding = status === "responding";
  const isThinking = status === "thinking";
  const canSend = isModelLoaded && message.trim().length > 0 && !isThinking;

  const placeholder = isModelLoaded
    ? "Type a message... (Enter to send, Shift+Enter for new line)"
    : "Waiting for model to load...";

  return (
    <div className="chat-input-area">
      <textarea
        rows={1}
        ref={textareaRef}
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        disabled={!isModelLoaded || isThinking}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        style={{
          flex: 1,
          resize: "vertical",
          minHeight: "23px",
          maxHeight: "120px",
        }}
      />
      {isResponding ? (
        <button
          className="send-btn"
          onClick={handleAbort}
          style={{
            alignSelf: "flex-end",
            height: "23px",
            minWidth: "60px",
          }}
          title="Stop generating"
        >
          ■ Stop
        </button>
      ) : (
        <button
          className="send-btn"
          disabled={!canSend}
          onClick={handleSend}
          style={{
            alignSelf: "flex-end",
            height: "23px",
            minWidth: "60px",
          }}
          title="Send message"
        >
          Send ➤
        </button>
      )}
    </div>
  );
}
