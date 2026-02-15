import React from "react";
import { useBubbleView } from "../contexts/BubbleViewContext";
import { useSharedState } from "../contexts/SharedStateContext";
import { Progress } from "./Progress";
import { isModelDownloading, isModelReady } from "../../helpers/model-helpers";
import { prettyDownloadSpeed } from "../helpers/convert-download-speed";

export const WelcomeMessageContent: React.FC = () => {
  const { setCurrentView } = useBubbleView();
  const { models } = useSharedState();

  // Find if any model is currently downloading
  const downloadingModel = Object.values(models || {}).find(isModelDownloading);
  // Check if any model is ready
  const readyModel = Object.values(models || {}).find(isModelReady);

  return (
    <div className="welcome-content">
      <strong>Welcome to Klippy!</strong>
      <p>
        This little app is a love letter and homage to the late, great Clippy,
        the assistant from Microsoft Office 1997. It is <i>not</i>{" "}
        affiliated, approved, or supported by Microsoft. Consider it software
        art or satire.
      </p>
      <p>
        Klippy runs a Large Language Model (LLM) locally on your computer,
        so you can chat with it completely offline and privately.
      </p>
      <p>
        It supports models from Google (Gemma3), Meta (Llama3), and Microsoft (Phi-4 Mini).
        We've started downloading the smallest model in the background.
      </p>
      <p style={{ fontSize: "0.9em", color: "#555" }}>
        💡 <strong>Tip:</strong> Click on Klippy's head to open or close this chat window.
      </p>

      {downloadingModel && (
        <div className="download-status">
          <p>
            ⬇ Downloading <strong>{downloadingModel.name}</strong>... (
            {prettyDownloadSpeed(
              downloadingModel.downloadState?.currentBytesPerSecond || 0,
            )}
            /s)
          </p>
          <Progress
            progress={downloadingModel.downloadState?.percentComplete || 0}
          />
        </div>
      )}

      {!downloadingModel && readyModel && (
        <div className="download-status" style={{ borderColor: "#c3e6c3" }}>
          <p style={{ color: "green", fontWeight: "bold", margin: 0 }}>
            ✓ {readyModel.name} is ready! You can now start chatting.
          </p>
        </div>
      )}

      <button onClick={() => setCurrentView("settings")} style={{ marginTop: 8 }}>
        ⚙ Open Settings
      </button>
    </div>
  );
};
