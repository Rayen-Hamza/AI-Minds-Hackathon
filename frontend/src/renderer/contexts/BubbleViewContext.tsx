import React, { createContext, useContext, useEffect, useState } from "react";
import { klippyApi } from "../klippyApi";

export type BubbleView =
  | "chat"
  | "chats"
  | "settings"
  | "settings-general"
  | "settings-model"
  | "settings-parameters"
  | "settings-advanced"
  | "settings-about";

type BubbleViewContextType = {
  currentView: BubbleView;
  setCurrentView: (view: BubbleView) => void;
};

const BubbleViewContext = createContext<BubbleViewContextType | undefined>(
  undefined,
);

export const BubbleViewProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [currentView, setCurrentView] = useState<BubbleView>("chat");

  useEffect(() => {
    klippyApi.offSetBubbleView();
    klippyApi.onSetBubbleView((view: BubbleView) => {
      setCurrentView(view);
    });

    return () => {
      klippyApi.offSetBubbleView();
    };
  }, []);

  return (
    <BubbleViewContext.Provider value={{ currentView, setCurrentView }}>
      {children}
    </BubbleViewContext.Provider>
  );
};

export const useBubbleView = () => {
  const context = useContext(BubbleViewContext);
  if (context === undefined) {
    throw new Error("useBubbleView must be used within a BubbleViewProvider");
  }
  return context;
};
