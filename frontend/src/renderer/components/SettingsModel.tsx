import { Column, TableView } from "./TableView";
import { Progress } from "./Progress";
import React, { useState } from "react";
import { useSharedState } from "../contexts/SharedStateContext";
import { klippyApi } from "../klippyApi";
import { prettyDownloadSpeed } from "../helpers/convert-download-speed";
import { ManagedModel } from "../../models";
import { isModelDownloading } from "../../helpers/model-helpers";

export const SettingsModel: React.FC = () => {
  const { models, settings } = useSharedState();
  const [selectedIndex, setSelectedIndex] = useState<number>(0);

  const columns: Array<Column> = [
    { key: "default", header: "Loaded", width: 50 },
    { key: "name", header: "Name" },
    {
      key: "size",
      header: "Size",
      render: (row) => `${row.size.toLocaleString()} MB`,
    },
    { key: "company", header: "Company" },
    { key: "downloaded", header: "Downloaded" },
  ];

  const modelKeys = Object.keys(models || {});
  const data = modelKeys.map((modelKey) => {
    const model = models?.[modelKey as keyof typeof models];

    return {
      default: model?.name === settings.selectedModel ? "ｘ" : "",
      name: model?.name,
      company: model?.company,
      size: model?.size,
      downloaded: model.downloaded ? "Yes" : "No",
    };
  });

  // Variables
  const selectedModel =
    models?.[modelKeys[selectedIndex] as keyof typeof models] || null;
  const isDownloading = isModelDownloading(selectedModel);
  const isDefaultModel = selectedModel?.name === settings.selectedModel;

  // Handlers
  // ---------------------------------------------------------------------------
  const handleRowSelect = (index: number) => {
    setSelectedIndex(index);
  };

  const handleDownload = async () => {
    if (selectedModel) {
      await klippyApi.downloadModelByName(data[selectedIndex].name);
    }
  };

  const handleDeleteOrRemove = async () => {
    if (selectedModel?.imported) {
      await klippyApi.removeModelByName(selectedModel.name);
    } else if (selectedModel) {
      await klippyApi.deleteModelByName(selectedModel.name);
    }
  };

  const handleMakeDefault = async () => {
    if (selectedModel) {
      klippyApi.setState("settings.selectedModel", selectedModel.name);
    }
  };

  return (
    <div>
      <p>
        Select the model for your chat. Larger models are more capable but
        slower and use more memory. Klippy uses the GGUF format.{" "}
        <a
          href="https://github.com/felixrieseberg/clippy?tab=readme-ov-file#downloading-more-models"
          target="_blank"
        >
          Learn more →
        </a>
      </p>

      <button
        style={{ marginBottom: 10 }}
        onClick={() => klippyApi.addModelFromFile()}
      >
        + Add model from file
      </button>
      <TableView
        columns={columns}
        data={data}
        onRowSelect={handleRowSelect}
        initialSelectedIndex={selectedIndex}
      />

      {selectedModel && (
        <div
          className="model-details sunken-panel"
          style={{ marginTop: "16px", padding: "12px" }}
        >
          <strong>{selectedModel.name}</strong>
          {isDefaultModel && (
            <span
              style={{
                marginLeft: "8px",
                fontSize: "0.8em",
                color: "green",
                fontWeight: "normal",
              }}
            >
              ✓ Active
            </span>
          )}

          {selectedModel.description && <p>{selectedModel.description}</p>}

          {selectedModel.homepage && (
            <p>
              <a
                href={selectedModel.homepage}
                target="_blank"
                rel="noopener noreferrer"
              >
                Visit Homepage →
              </a>
            </p>
          )}

          <div className="model-actions">
            {!selectedModel.downloaded ? (
              <button disabled={isDownloading} onClick={handleDownload}>
                ⬇ Download Model
              </button>
            ) : (
              <>
                <button
                  disabled={isDownloading || isDefaultModel}
                  onClick={handleMakeDefault}
                >
                  {isDefaultModel
                    ? "✓ Currently Active"
                    : "Use This Model"}
                </button>
                <button onClick={handleDeleteOrRemove}>
                  {selectedModel?.imported ? "Remove" : "Delete"}
                </button>
              </>
            )}
          </div>
          <SettingsModelDownload model={selectedModel} />
        </div>
      )}
    </div>
  );
};

const SettingsModelDownload: React.FC<{
  model?: ManagedModel;
}> = ({ model }) => {
  if (!model || !isModelDownloading(model)) {
    return null;
  }

  const downloadSpeed = prettyDownloadSpeed(
    model?.downloadState?.currentBytesPerSecond || 0,
  );

  return (
    <div style={{ marginTop: "12px" }}>
      <div className="download-status">
        <p>
          ⬇ Downloading <strong>{model.name}</strong>... ({downloadSpeed}/s)
        </p>
        <Progress progress={model.downloadState?.percentComplete || 0} />
      </div>
    </div>
  );
};
