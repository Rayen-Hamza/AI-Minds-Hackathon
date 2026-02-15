import Markdown from "react-markdown";
import { useState } from "react";
import questionIcon from "../images/icons/question.png";
import iconV2 from "../../../assets/icon_v2.png";
import { MessageRecord } from "../../types/interfaces";

export interface Message extends MessageRecord {
  id: string;
  content?: string;
  children?: React.ReactNode;
  createdAt: number;
  sender: "user" | "klippy";
  sourceFiles?: string[];
  confidence?: number;
  hasGraphReasoning?: boolean;
  hasRagContext?: boolean;
  entitiesFound?: string[];
}

function formatTime(timestamp: number): string {
  const date = new Date(timestamp);
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

// Check if a file path is an image
function isImageFile(filePath: string): boolean {
  const imageExtensions = [
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".webp",
    ".svg",
  ];
  const lowerPath = filePath.toLowerCase();
  return imageExtensions.some((ext) => lowerPath.endsWith(ext));
}

// Get filename from path
function getFileName(filePath: string): string {
  return filePath.split(/[/\\]/).pop() || filePath;
}

// Source files component with image previews
function SourceFiles({ files }: { files: string[] }) {
  const [expandedImage, setExpandedImage] = useState<string | null>(null);

  if (!files || files.length === 0) return null;

  const imageFiles = files.filter(isImageFile);
  const otherFiles = files.filter((f) => !isImageFile(f));

  return (
    <div
      style={{
        marginTop: "8px",
        padding: "8px",
        backgroundColor: "rgba(0,0,0,0.03)",
        borderRadius: "6px",
        fontSize: "0.85em",
      }}
    >
      <div
        style={{
          fontWeight: "600",
          marginBottom: "6px",
          color: "#666",
          display: "flex",
          alignItems: "center",
          gap: "4px",
        }}
      >
        📎 Sources ({files.length})
      </div>

      {/* Image previews */}
      {imageFiles.length > 0 && (
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: "8px",
            marginBottom: otherFiles.length > 0 ? "8px" : 0,
          }}
        >
          {imageFiles.map((file, idx) => (
            <div
              key={idx}
              style={{
                position: "relative",
                cursor: "pointer",
              }}
              onClick={() =>
                setExpandedImage(expandedImage === file ? null : file)
              }
            >
              <img
                src={`file://${file}`}
                alt={getFileName(file)}
                style={{
                  width: expandedImage === file ? "200px" : "60px",
                  height: expandedImage === file ? "auto" : "60px",
                  objectFit: "cover",
                  borderRadius: "4px",
                  border: "1px solid #ddd",
                  transition: "all 0.2s ease",
                }}
                onError={(e) => {
                  // Fallback if image can't be loaded
                  (e.target as HTMLImageElement).style.display = "none";
                }}
              />
              <div
                style={{
                  fontSize: "0.7em",
                  color: "#888",
                  maxWidth: expandedImage === file ? "200px" : "60px",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                  marginTop: "2px",
                }}
              >
                {getFileName(file)}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Other files list */}
      {otherFiles.length > 0 && (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "2px",
          }}
        >
          {otherFiles.map((file, idx) => (
            <div
              key={idx}
              style={{
                color: "#555",
                padding: "2px 4px",
                backgroundColor: "rgba(0,0,0,0.02)",
                borderRadius: "3px",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
              title={file}
            >
              📄 {getFileName(file)}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// Metadata badges component
function MetadataBadges({ message }: { message: Message }) {
  const badges = [];

  if (message.hasGraphReasoning) {
    badges.push({ label: "🔗 Graph", color: "#e3f2fd", textColor: "#1565c0" });
  }
  if (message.hasRagContext) {
    badges.push({ label: "📚 RAG", color: "#f3e5f5", textColor: "#7b1fa2" });
  }
  if (message.confidence !== undefined && message.confidence !== null) {
    const confPct = Math.round(message.confidence * 100);
    const confColor =
      confPct >= 70 ? "#e8f5e9" : confPct >= 40 ? "#fff3e0" : "#ffebee";
    const textColor =
      confPct >= 70 ? "#2e7d32" : confPct >= 40 ? "#ef6c00" : "#c62828";
    badges.push({ label: `${confPct}%`, color: confColor, textColor });
  }

  if (badges.length === 0) return null;

  return (
    <div
      style={{
        display: "flex",
        gap: "4px",
        marginTop: "6px",
        flexWrap: "wrap",
      }}
    >
      {badges.map((badge, idx) => (
        <span
          key={idx}
          style={{
            fontSize: "0.7em",
            padding: "2px 6px",
            borderRadius: "10px",
            backgroundColor: badge.color,
            color: badge.textColor,
            fontWeight: "500",
          }}
        >
          {badge.label}
        </span>
      ))}
      {message.entitiesFound && message.entitiesFound.length > 0 && (
        <span
          style={{
            fontSize: "0.7em",
            padding: "2px 6px",
            borderRadius: "10px",
            backgroundColor: "#fff8e1",
            color: "#f57f17",
            fontWeight: "500",
          }}
          title={message.entitiesFound.join(", ")}
        >
          🏷️ {message.entitiesFound.length} entities
        </span>
      )}
    </div>
  );
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
        src={isUser ? questionIcon : iconV2}
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

          {/* Show metadata badges for Klippy messages */}
          {!isUser && !isStreaming && <MetadataBadges message={message} />}

          {/* Show source files with image previews */}
          {!isUser &&
            !isStreaming &&
            message.sourceFiles &&
            message.sourceFiles.length > 0 && (
              <SourceFiles files={message.sourceFiles} />
            )}
        </div>
      </div>
    </div>
  );
}
