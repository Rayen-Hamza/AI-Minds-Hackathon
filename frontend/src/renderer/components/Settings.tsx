import { useEffect, useState } from "react";

import { TabList } from "./TabList";
import { BubbleView, useBubbleView } from "../contexts/BubbleViewContext";
import { BubbleWindowBottomBar } from "./BubbleWindowBottomBar";
import { SettingsAdvanced } from "./SettingsAdvanced";
import { SettingsAppearance } from "./SettingsAppearance";
import { SettingsAbout } from "./SettingsAbout";
import { SettingsPreferences } from "./SettingsPreferences";

export type SettingsTab = "appearance" | "preferences" | "advanced" | "about";

export type SettingsProps = {
  onClose: () => void;
};

export const Settings: React.FC<SettingsProps> = ({ onClose }) => {
  const { currentView, setCurrentView } = useBubbleView();
  const [activeTab, setActiveTab] = useState<SettingsTab>(
    bubbleViewToSettingsTab(currentView),
  );

  useEffect(() => {
    const newTab = bubbleViewToSettingsTab(currentView);

    if (newTab !== activeTab) {
      setActiveTab(newTab);
    }
  }, [currentView, activeTab]);

  const tabs = [
    { label: "Appearance", key: "appearance", content: <SettingsAppearance /> },
    { label: "Preferences", key: "preferences", content: <SettingsPreferences /> },
    { label: "Advanced", key: "advanced", content: <SettingsAdvanced /> },
    { label: "About", key: "about", content: <SettingsAbout /> },
  ];

  return (
    <>
      <TabList
        tabs={tabs}
        activeTab={activeTab}
        onTabChange={(tab) => setCurrentView(`settings-${tab}` as BubbleView)}
      />
      <BubbleWindowBottomBar>
        <button onClick={onClose} title="Return to chat">
          ← Back to Chat
        </button>
      </BubbleWindowBottomBar>
    </>
  );
};

/**
 * Converts a BubbleView to a SettingsTab.
 *
 * @param view - The BubbleView to convert.
 * @returns The SettingsTab.
 */
function bubbleViewToSettingsTab(view: BubbleView): SettingsTab {
  if (!view || !view.includes("settings")) {
    return "appearance";
  }

  const settingsTab = view.replace(/settings-?/, "");
  const settingsTabs = [
    "appearance",
    "preferences",
    "advanced",
    "about",
  ] as const;

  if (settingsTabs.includes(settingsTab as SettingsTab)) {
    return settingsTab as SettingsTab;
  }

  return "appearance";
}
