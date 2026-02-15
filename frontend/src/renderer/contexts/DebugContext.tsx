import { createContext, useContext, useEffect, useState } from "react";

import { klippyApi } from "../klippyApi";
import { DebugState, EMPTY_DEBUG_STATE } from "../../debugState";

export const DebugContext = createContext<DebugState>(EMPTY_DEBUG_STATE);

export const DebugProvider = ({ children }: { children: React.ReactNode }) => {
  const [debugState, setDebugState] = useState<DebugState>(EMPTY_DEBUG_STATE);

  useEffect(() => {
    const fetchDebugState = async () => {
      const state = await klippyApi.getFullDebugState();
      setDebugState(state);
    };
    fetchDebugState();

    klippyApi.offDebugStateChanged();
    klippyApi.onDebugStateChanged((state) => {
      setDebugState(state);
    });

    return () => {
      klippyApi.offDebugStateChanged();
    };
  }, []);

  return (
    <DebugContext.Provider value={debugState}>{children}</DebugContext.Provider>
  );
};

export const useDebugState = () => {
  const context = useContext(DebugContext);

  if (!context) {
    throw new Error("useDebugState must be used within a DebugProvider");
  }

  return context;
};
