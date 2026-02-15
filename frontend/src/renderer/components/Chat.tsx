import { useState } from "react";

import { Message } from "./Message";
import { ChatInput } from "./ChatInput";
import { useChat } from "../contexts/ChatContext";
import { electronAi } from "../klippyApi";

export type ChatProps = {
  style?: React.CSSProperties;
};

export function Chat({ style }: ChatProps) {
  const { setStatus, status, messages, addMessage, currentChatRecord } =
    useChat();
  const [streamingMessageContent, setStreamingMessageContent] =
    useState<string>("");
  const [lastRequestUUID, setLastRequestUUID] = useState<string>(
    crypto.randomUUID(),
  );

  const handleAbortMessage = () => {
    electronAi.abortRequest(lastRequestUUID);
  };

  const handleSendMessage = async (message: string) => {
    if (status !== "idle") {
      return;
    }

    const userMessage: Message = {
      id: crypto.randomUUID(),
      content: message,
      sender: "user",
      createdAt: Date.now(),
    };

    await addMessage(userMessage);
    setStreamingMessageContent("");
    setStatus("thinking");

    try {
      const requestUUID = crypto.randomUUID();
      setLastRequestUUID(requestUUID);

      // Call the agent chat endpoint with session_id
      setStatus("responding");
      const response = await window.klippy.agentChat(
        message,
        currentChatRecord.id,
      );

      // Extract the response text
      let responseText = "";
      let sourceFiles: string[] = [];
      let confidence: number | undefined;
      let hasGraphReasoning = false;
      let hasRagContext = false;
      let entitiesFound: string[] = [];

      if (response && response.response) {
        responseText = response.response;
        // Extract metadata from response
        sourceFiles = response.source_files || [];
        confidence = response.confidence;
        hasGraphReasoning = response.has_graph_reasoning || false;
        hasRagContext = response.has_rag_context || false;
        entitiesFound = response.entities_found || [];
      } else if (typeof response === "string") {
        responseText = response;
      } else {
        responseText = JSON.stringify(response, null, 2);
      }

      // Add the assistant's response to the messages
      const assistantMessage: Message = {
        id: crypto.randomUUID(),
        content: responseText,
        sender: "klippy",
        createdAt: Date.now(),
        sourceFiles,
        confidence,
        hasGraphReasoning,
        hasRagContext,
        entitiesFound,
      };

      addMessage(assistantMessage);
    } catch (error) {
      console.error("Error calling agent chat:", error);

      // Add error message to chat
      const errorMessage: Message = {
        id: crypto.randomUUID(),
        content: `Error: ${error instanceof Error ? error.message : "Failed to get response from agent"}`,
        sender: "klippy",
        createdAt: Date.now(),
      };

      addMessage(errorMessage);
    } finally {
      setStreamingMessageContent("");
      setStatus("idle");
    }
  };

  return (
    <div style={style} className="chat-container">
      {messages.length === 0 && status === "idle" && (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            padding: "40px 20px",
            color: "#888",
            textAlign: "center",
          }}
        >
          <p style={{ fontSize: "1.1em", marginBottom: "4px" }}>
            Ask Klippy anything!
          </p>
          <p style={{ fontSize: "0.85em" }}>
            Type a message below to get started.
          </p>
        </div>
      )}
      {messages.map((message) => (
        <Message key={message.id} message={message} />
      ))}
      {status === "thinking" && (
        <div className="status-indicator" style={{ padding: "8px 0" }}>
          <span className="status-dot status-dot--thinking" />
          Klippy is thinking...
        </div>
      )}
      {status === "responding" && (
        <Message
          message={{
            id: "streaming",
            content: streamingMessageContent,
            sender: "klippy",
            createdAt: Date.now(),
          }}
        />
      )}
      <ChatInput onSend={handleSendMessage} onAbort={handleAbortMessage} />
    </div>
  );
}
