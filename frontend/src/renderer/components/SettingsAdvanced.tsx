import { klippyApi } from "../klippyApi";
import { useSharedState } from "../contexts/SharedStateContext";
import { Checkbox } from "./Checkbox";

export const SettingsAdvanced: React.FC = () => {
  const { settings } = useSharedState();

  return (
    <div>
      <fieldset>
        <legend>Automatic Updates</legend>
        <Checkbox
          id="autoUpdates"
          label="Automatically keep Klippy up to date"
          checked={!settings.disableAutoUpdate}
          onChange={(checked) => {
            klippyApi.setState("settings.disableAutoUpdate", !checked);
          }}
        />

        <button
          style={{ marginTop: "10px" }}
          onClick={() => klippyApi.checkForUpdates()}
        >
          Check for Updates
        </button>
      </fieldset>
      <fieldset>
        <legend>Configuration</legend>
        <p className="helper-text">
          Edit configuration files directly. Restart Klippy after changes.
        </p>
        <div style={{ display: "flex", gap: "8px" }}>
          <button onClick={klippyApi.openStateInEditor}>
            Open Config
          </button>
          <button onClick={klippyApi.openDebugStateInEditor}>
            Open Debug Config
          </button>
        </div>
      </fieldset>
      <fieldset>
        <legend>Danger Zone</legend>
        <p className="helper-text">
          This will permanently delete all downloaded models. This cannot be undone.
        </p>
        <button onClick={klippyApi.deleteAllModels}>Delete All Models</button>
      </fieldset>
    </div>
  );
};
