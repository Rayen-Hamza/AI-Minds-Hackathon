import Markdown from "react-markdown";
import questionIcon from "../images/icons/question.png";
import defaultKlippy from "../images/animations/Default.png";
import { MessageRecord } from "../../types/interfaces";
import { klippyApi } from "../klippyApi";

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
                  img: ({ node, ...props }) => (
                    <img
                      {...props}
                      style={{
                        maxWidth: "100%",
                        height: "auto",
                        borderRadius: "8px",
                        marginTop: "8px",
                        marginBottom: "8px",
                      }}
                      alt={props.alt || "Image"}
                    />
                  ),
                  text: ({ children }) => {
                    const handleOpenFile = (filePath: string) => {
                      const cleanPath = filePath.replace(/^file:\/\//, '').trim();
                      console.log('Opening file from text:', cleanPath);
                      klippyApi.openFileInFolder(cleanPath);
                    };

                    const content = String(children);
                    // Match any absolute path (starting with /)
                    const filePathRegex = /(\/[^\s]+)/g;
                    const matches = content.match(filePathRegex);

                    if (!matches || matches.length === 0) {
                      return <>{children}</>;
                    }

                    const parts = content.split(filePathRegex);
                    const processedContent = parts.map((part, index) => {
                      if (part && part.startsWith('/') && part.length > 1) {
                        return (
                          <button
                            key={index}
                            onClick={() => handleOpenFile(part)}
                            style={{
                              display: "inline-flex",
                              alignItems: "center",
                              padding: "4px 12px",
                              marginLeft: "4px",
                              marginRight: "4px",
                              backgroundColor: "#1a56db",
                              color: "white",
                              border: "none",
                              borderRadius: "4px",
                              cursor: "pointer",
                              fontSize: "0.85em",
                              fontWeight: "500",
                              fontFamily: "monospace",
                            }}
                            onMouseOver={(e) => {
                              e.currentTarget.style.backgroundColor = "#1347c4";
                            }}
                            onMouseOut={(e) => {
                              e.currentTarget.style.backgroundColor = "#1a56db";
                            }}
                            title={`Click to open: ${part}`}
                          >
                            📁 {part.split('/').pop()}
                          </button>
                        );
                      }
                      if (part) {
                        return <span key={index}>{part}</span>;
                      }
                      return null;
                    });

                    return <>{processedContent}</>;
                  },
                  p: ({ node, children, ...props }) => {
                    const handleOpenFile = (filePath: string) => {
                      const cleanPath = filePath.replace(/^file:\/\//, '').trim();
                      console.log('Opening file:', cleanPath);
                      klippyApi.openFileInFolder(cleanPath);
                    };

                    // Convert children to string and detect file paths
                    const content = String(children);

                    // Regex to match file paths - match any absolute path starting with /
                    const filePathRegex = /(\/[^\s]+)/g;

                    // Find all matches
                    const matches = content.match(filePathRegex);

                    // If no file paths found, return regular paragraph
                    if (!matches || matches.length === 0) {
                      return <p {...props}>{children}</p>;
                    }

                    // Split and process
                    const parts = content.split(filePathRegex);

                    // Process parts and create buttons for file paths
                    const processedContent = parts.map((part, index) => {
                      // Check if this part is a file path (starts with /)
                      if (part && part.startsWith('/') && part.length > 1) {
                        return (
                          <button
                            key={index}
                            onClick={() => handleOpenFile(part)}
                            style={{
                              display: "inline-flex",
                              alignItems: "center",
                              padding: "4px 12px",
                              marginLeft: "4px",
                              marginRight: "4px",
                              backgroundColor: "#1a56db",
                              color: "white",
                              border: "none",
                              borderRadius: "4px",
                              cursor: "pointer",
                              fontSize: "0.85em",
                              fontWeight: "500",
                              fontFamily: "monospace",
                            }}
                            onMouseOver={(e) => {
                              e.currentTarget.style.backgroundColor = "#1347c4";
                            }}
                            onMouseOut={(e) => {
                              e.currentTarget.style.backgroundColor = "#1a56db";
                            }}
                            title={`Click to open: ${part}`}
                          >
                            📁 {part.split('/').pop()}
                          </button>
                        );
                      }
                      // Regular text
                      if (part) {
                        return <span key={index}>{part}</span>;
                      }
                      return null;
                    });

                    return <p {...props}>{processedContent}</p>;
                  },
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
