import { useCallback, useState } from "react";

import { klippyApi } from "../klippyApi";
import { Chat } from "./Chat";
import { Settings } from "./Settings";
import { useBubbleView } from "../contexts/BubbleViewContext";
import { Chats } from "./Chats";
import { useChat } from "../contexts/ChatContext";

export function Bubble() {
  const { currentView, setCurrentView } = useBubbleView();
  const [isMaximized, setIsMaximized] = useState(false);
  const { status, startNewChat } = useChat();

  const containerStyle = {
    width: "calc(100% - 6px)",
    height: "calc(100% - 6px)",
    margin: 0,
    overflow: "hidden",
  };

  const chatStyle = {
    padding: "15px",
    display: "flex",
    flexDirection: "column" as const,
    justifyContent: "flex-end",
    minHeight: "calc(100% - 35px)",
    overflowAnchor: "none" as const,
  };

  const scrollAnchoredAtBottomStyle = {
    display: "flex",
    flexDirection: "column-reverse" as const,
  };

  let content = null;

  if (currentView === "chat") {
    content = <Chat style={chatStyle} />;
  } else if (currentView.startsWith("settings")) {
    content = <Settings onClose={() => setCurrentView("chat")} />;
  } else if (currentView === "chats") {
    content = <Chats onClose={() => setCurrentView("chat")} />;
  }

  const handleSettingsClick = useCallback(() => {
    if (currentView.startsWith("settings")) {
      setCurrentView("chat");
    } else {
      setCurrentView("settings");
    }
  }, [setCurrentView, currentView]);

  const handleChatsClick = useCallback(() => {
    if (currentView === "chats") {
      setCurrentView("chat");
    } else {
      setCurrentView("chats");
    }
  }, [setCurrentView, currentView]);

  const handleNewChat = useCallback(async () => {
    await startNewChat();
    setCurrentView("chat");
  }, [setCurrentView, startNewChat]);

  // Status label for the status bar
  const getStatusText = () => {
    switch (status) {
      case "thinking":
        return "Klippy is thinking...";
      case "responding":
        return "Klippy is responding...";
      case "welcome":
        return "Welcome!";
      case "idle":
        return "Ready";
      case "goodbye":
        return "Goodbye!";
      default:
        return "";
    }
  };

  const getStatusDotClass = () => {
    switch (status) {
      case "thinking":
        return "status-dot status-dot--thinking";
      case "responding":
        return "status-dot status-dot--responding";
      case "idle":
        return "status-dot status-dot--idle";
      default:
        return "status-dot";
    }
  };

  return (
    <div className="bubble-container window" style={containerStyle}>
      <div className="app-drag title-bar">
        <div className="title-bar-text">Chat with Klippy</div>
        <div className="title-bar-controls app-no-drag">
          <button
            style={{
              marginRight: "4px",
              paddingLeft: "8px",
              paddingRight: "8px",
            }}
            onClick={handleNewChat}
            title="Start a new chat"
          >
            New
          </button>
          <button
            style={{
              marginRight: "4px",
              paddingLeft: "8px",
              paddingRight: "8px",
            }}
            onClick={handleChatsClick}
            title="Chat history"
          >
            History
          </button>
          <button
            style={{
              marginRight: "8px",
              paddingLeft: "8px",
              paddingRight: "8px",
            }}
            onClick={handleSettingsClick}
            title="Settings"
          >
            ⚙
          </button>
          <button
            aria-label="Minimize"
            onClick={() => klippyApi.minimizeChatWindow()}
          ></button>
          <button
            aria-label={isMaximized ? "Restore" : "Maximize"}
            onClick={() => {
              klippyApi.maximizeChatWindow();
              setIsMaximized(!isMaximized);
            }}
          ></button>
          <button
            aria-label="Close"
            onClick={() => klippyApi.toggleChatWindow()}
          ></button>
        </div>
      </div>
      <div
        className="window-content"
        style={currentView === "chat" ? scrollAnchoredAtBottomStyle : {}}
      >
        {content}
      </div>
      {currentView === "chat" && (
        <div
          className="status-bar"
          style={{ fontSize: "0.85em" }}
        >
          <p className="status-bar-field">
            <span className={getStatusDotClass()} style={{ marginRight: 6 }} />
            {getStatusText()}
          </p>
        </div>
      )}
    </div>
  );
}
