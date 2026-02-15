import { DEFAULT_SETTINGS, SettingsState } from "../../sharedState";
import { klippyApi } from "../klippyApi";
import { useSharedState } from "../contexts/SharedStateContext";
import { Checkbox } from "./Checkbox";

export const SettingsAppearance: React.FC = () => {
  const { settings } = useSharedState();

  const onChangeFontSize = (event: React.ChangeEvent<HTMLInputElement>) => {
    const newSize = parseInt(event.target.value, 10);

    if (!isNaN(newSize)) {
      klippyApi.setState("settings.defaultFontSize", newSize);
    }
  };

  const onReset = () => {
    const defaultAppareanceSettings: SettingsState = {
      defaultFont: DEFAULT_SETTINGS.defaultFont,
      defaultFontSize: DEFAULT_SETTINGS.defaultFontSize,
      klippyAlwaysOnTop: DEFAULT_SETTINGS.klippyAlwaysOnTop,
      chatAlwaysOnTop: DEFAULT_SETTINGS.chatAlwaysOnTop,
      alwaysOpenChat: DEFAULT_SETTINGS.alwaysOpenChat,
      minimizeToTray: DEFAULT_SETTINGS.minimizeToTray,
    };

    for (const key in defaultAppareanceSettings) {
      klippyApi.setState(
        `settings.${key}`,
        defaultAppareanceSettings[key as keyof SettingsState],
      );
    }
  };

  return (
    <div>
      <fieldset>
        <legend>Window Options</legend>
        <Checkbox
          id="klippyAlwaysOnTop"
          label="Keep Klippy always on top of all other windows"
          checked={settings.klippyAlwaysOnTop}
          onChange={(checked) => {
            klippyApi.setState("settings.klippyAlwaysOnTop", checked);
          }}
        />
        <Checkbox
          id="chatAlwaysOnTop"
          label="Keep chat always on top of all other windows"
          checked={settings.chatAlwaysOnTop}
          onChange={(checked) => {
            klippyApi.setState("settings.chatAlwaysOnTop", checked);
          }}
        />
        <Checkbox
          id="alwaysOpenChat"
          label="Always open chat when Klippy starts"
          checked={settings.alwaysOpenChat}
          onChange={(checked) => {
            klippyApi.setState("settings.alwaysOpenChat", checked);
          }}
        />
        <Checkbox
          id="minimizeToTray"
          label="Minimize to system tray instead of closing"
          checked={settings.minimizeToTray}
          onChange={(checked) => {
            klippyApi.setState("settings.minimizeToTray", checked);
          }}
        />
      </fieldset>
      <fieldset>
        <legend>Font Options</legend>
        <div className="field-row" style={{ width: 300 }}>
          <label style={{ width: 100 }}>Font size:</label>
          <label>8px</label>
          <input
            type="range"
            min="8"
            max="20"
            step={1}
            value={settings.defaultFontSize}
            onChange={onChangeFontSize}
          />
          <label>20px</label>
        </div>
        <div className="field-row" style={{ width: 300 }}>
          <label htmlFor="defaultFont" style={{ width: 58 }}>
            Font:
          </label>
          <select
            id="defaultFont"
            value={settings.defaultFont}
            onChange={(event) => {
              klippyApi.setState("settings.defaultFont", event.target.value);
            }}
          >
            <option value="Pixelated MS Sans Serif">
              Pixelated MS Sans Serif
            </option>
            <option value="Comic Sans MS">Comic Sans MS</option>
            <option value="Tahoma">Tahoma</option>
            <option value="System Default">System Default</option>
          </select>
        </div>
      </fieldset>
      <button style={{ marginTop: 10 }} onClick={onReset}>
        Reset
      </button>
    </div>
  );
};
