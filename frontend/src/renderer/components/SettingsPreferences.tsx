import { useState } from "react";
import { Checkbox } from "./Checkbox";

export const SettingsPreferences: React.FC = () => {
  const [folders, setFolders] = useState({
    downloads: false,
    images: false,
    videos: false,
    documents: false,
  });
  const [customPath, setCustomPath] = useState("");
  const [aboutYourself, setAboutYourself] = useState("");

  const handleFolderChange = (folder: keyof typeof folders) => {
    return (checked: boolean) => {
      setFolders((prev) => ({ ...prev, [folder]: checked }));
    };
  };

  return (
    <div>
      <fieldset>
        <legend>Folder Access</legend>
        <p className="helper-text">
          Choose which folders the model is allowed to access on your system.
        </p>
        <Checkbox
          id="folder-downloads"
          label="Downloads"
          checked={folders.downloads}
          onChange={handleFolderChange("downloads")}
        />
        <Checkbox
          id="folder-images"
          label="Images"
          checked={folders.images}
          onChange={handleFolderChange("images")}
        />
        <Checkbox
          id="folder-videos"
          label="Videos"
          checked={folders.videos}
          onChange={handleFolderChange("videos")}
        />
        <Checkbox
          id="folder-documents"
          label="Documents"
          checked={folders.documents}
          onChange={handleFolderChange("documents")}
        />
      </fieldset>

      <fieldset>
        <legend>Custom Path</legend>
        <p className="helper-text">
          Specify an additional folder path the model can access.
        </p>
        <div className="field-row" style={{ gap: 8 }}>
          <input
            id="customPath"
            type="text"
            placeholder="C:\Users\You\MyFolder"
            value={customPath}
            onChange={(e) => setCustomPath(e.target.value)}
            style={{ flex: 1 }}
          />
        </div>
      </fieldset>

      <fieldset>
        <legend>Tell Us About Yourself</legend>
        <p className="helper-text">
          Help the model understand you better. Share your interests, work, or
          anything you'd like it to know so it can tailor responses to you.
        </p>
        <div className="field-row-stacked">
          <textarea
            id="aboutYourself"
            rows={6}
            style={{ resize: "vertical" }}
            placeholder="e.g. I'm a software engineer who loves hiking and sci-fi novels..."
            value={aboutYourself}
            onChange={(e) => setAboutYourself(e.target.value)}
          />
        </div>
      </fieldset>
    </div>
  );
};
