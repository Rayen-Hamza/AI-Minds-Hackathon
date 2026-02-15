import Markdown from "react-markdown";
import questionIcon from "../images/icons/question.png";
import defaultKlippy from "../images/animations/Default.png";
import { MessageRecord } from "../../types/interfaces";

export interface Message extends MessageRecord {
  id: string;
  content?: string;
  children?: React.ReactNode;
  createdAt: number;
  sender: "user" | "klippy";
}

function formatTime(timestamp: number): string {
  const date = new Date(timestamp);
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function Message({ message }: { message: Message }) {
  const isUser = message.sender === "user";
  const isStreaming = message.id === "streaming";

  return (
    <div
      className="message"
      style={{ display: "flex", alignItems: "flex-start" }}
    >
      <img
        src={isUser ? questionIcon : defaultKlippy}
        alt={isUser ? "You" : "Klippy"}
        style={{
          width: "28px",
          height: "28px",
          marginRight: "10px",
          marginTop: "2px",
          flexShrink: 0,
        }}
      />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "baseline",
            marginBottom: "2px",
          }}
        >
          <span
            style={{
              fontWeight: "bold",
              fontSize: "0.9em",
              color: isUser ? "#1a56db" : "#333",
            }}
          >
            {isUser ? "You" : "Klippy"}
          </span>
          {!isStreaming && (
            <span
              style={{
                fontSize: "0.75em",
                color: "#999",
                marginLeft: "8px",
                flexShrink: 0,
              }}
            >
              {formatTime(message.createdAt)}
            </span>
          )}
        </div>
        <div className={`message-bubble message-bubble--${message.sender}`}>
          <div className="message-content">
            {message.children ? (
              message.children
            ) : (
              <Markdown
                components={{
                  a: ({ node, ...props }) => (
                    <a target="_blank" rel="noopener noreferrer" {...props} />
                  ),
                }}
              >
                {message.content}
              </Markdown>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
