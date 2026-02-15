import { createContext, useContext, useEffect, useState, useRef } from "react";
import { DEFAULT_SETTINGS, SharedState } from "../../sharedState";
import { klippyApi } from "../klippyApi";
import { isModelDownloading } from "../../helpers/model-helpers";

const EMPTY_SHARED_STATE: SharedState = {
  models: {},
  settings: {
    ...DEFAULT_SETTINGS,
    selectedModel: undefined,
    systemPrompt: undefined,
  },
};

export const SharedStateContext =
  createContext<SharedState>(EMPTY_SHARED_STATE);

export const SharedStateProvider = ({
  children,
}: {
  children: React.ReactNode;
}) => {
  const [sharedState, setSharedState] =
    useState<SharedState>(EMPTY_SHARED_STATE);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    const fetchSharedState = async () => {
      const state = await klippyApi.getFullState();
      setSharedState(state);
    };

    fetchSharedState();

    klippyApi.offStateChanged();
    klippyApi.onStateChanged((state) => {
      setSharedState(state);
    });

    return () => {
      klippyApi.offStateChanged();
    };
  }, []);

  useEffect(() => {
    // Check if any model is downloading
    const isAnyModelDownloading = Object.values(sharedState.models || {}).some(
      isModelDownloading,
    );

    // Start interval if any model is downloading
    if (isAnyModelDownloading && !intervalRef.current) {
      intervalRef.current = setInterval(() => {
        klippyApi.updateModelState();
      }, 250);
    }
    // Stop interval if no model is downloading
    else if (!isAnyModelDownloading && intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }

    // Cleanup on unmount
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [sharedState.models]);

  return (
    <SharedStateContext.Provider value={sharedState}>
      {children}
    </SharedStateContext.Provider>
  );
};

export const useSharedState = () => {
  const sharedState = useContext(SharedStateContext);

  if (!sharedState) {
    throw new Error("useSharedState must be used within a SharedStateProvider");
  }

  return sharedState;
};
