import { klippyApi } from "../klippyApi";
import { useSharedState } from "../contexts/SharedStateContext";

interface ErrorLoadModelMessageContentProps {
  error: string;
}

export const ErrorLoadModelMessageContent: React.FC<
  ErrorLoadModelMessageContentProps
> = ({ error }) => {
  const { settings } = useSharedState();

  const handleCopyDebugInfo = async () => {
    klippyApi.clipboardWrite({
      text: JSON.stringify(
        {
          error,
          settings,
          state: await klippyApi.getDebugInfo(),
        },
        null,
        2,
      ),
    });
  };

  return (
    <div className="error-content">
      <p>
        ⚠ Klippy failed to load the model. This could be an
        issue with Klippy itself, the selected model, or your system.
      </p>
      <p>
        You can report this error at{" "}
        <a
          href="https://github.com/felixrieseberg/clippy/issues"
          target="_blank"
        >
          github.com/felixrieseberg/clippy/issues
        </a>
        . Please include both the error message and the debug information.
      </p>
      <div style={{ display: "flex", gap: "8px", marginBottom: "8px" }}>
        <button onClick={handleCopyDebugInfo}>📋 Copy Debug Info</button>
      </div>
      <details>
        <summary style={{ cursor: "pointer", color: "#666" }}>Show error details</summary>
        <pre>{`${error}`}</pre>
      </details>
    </div>
  );
};
