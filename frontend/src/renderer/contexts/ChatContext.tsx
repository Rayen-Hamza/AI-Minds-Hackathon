import {
  createContext,
  useContext,
  useState,
  ReactNode,
  useEffect,
  useCallback,
} from "react";
import { Message } from "../components/Message";
import { klippyApi } from "../klippyApi";
import { ChatRecord, MessageRecord } from "../../types/interfaces";

// Backend handles all model-related types and configuration

type KlippyNamedStatus =
  | "welcome"
  | "idle"
  | "responding"
  | "thinking"
  | "goodbye";

export type ChatContextType = {
  messages: Message[];
  addMessage: (message: Message) => Promise<void>;
  setMessages: (messages: Message[]) => void;
  animationKey: string;
  setAnimationKey: (animationKey: string) => void;
  status: KlippyNamedStatus;
  setStatus: (status: KlippyNamedStatus) => void;
  isModelLoaded: boolean;
  isChatWindowOpen: boolean;
  setIsChatWindowOpen: (isChatWindowOpen: boolean) => void;
  chatRecords: Record<string, ChatRecord>;
  currentChatRecord: ChatRecord;
  selectChat: (chatId: string) => void;
  startNewChat: () => Promise<void>;
  deleteChat: (chatId: string) => Promise<void>;
  deleteAllChats: () => Promise<void>;
};

export const ChatContext = createContext<ChatContextType | undefined>(
  undefined,
);

export function ChatProvider({ children }: { children: ReactNode }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [currentChatRecord, setCurrentChatRecord] = useState<ChatRecord>({
    id: crypto.randomUUID(),
    createdAt: Date.now(),
    updatedAt: Date.now(),
    preview: "",
  });
  const [chatRecords, setChatRecords] = useState<Record<string, ChatRecord>>(
    {},
  );
  const [animationKey, setAnimationKey] = useState<string>("");
  const [status, setStatus] = useState<KlippyNamedStatus>("welcome");
  // Model is handled by backend, so always set to true
  const [isModelLoaded] = useState(true);
  const [isChatWindowOpen, setIsChatWindowOpen] = useState(false);


  const addMessage = useCallback(
    async (message: Message) => {
      setMessages((prevMessages) => [...prevMessages, message]);
    },
    [currentChatRecord, messages],
  );

  const selectChat = useCallback(
    async (chatId: string) => {
      try {
        const chatWithMessages = await klippyApi.getChatWithMessages(chatId);

        if (chatWithMessages) {
          setMessages(chatWithMessages.messages);
          setCurrentChatRecord(chatWithMessages.chat);
        }

        // Model loading is handled by backend, no need to load here
        // await loadModel(
        //   messagesToInitialPrompts(chatWithMessages?.messages || []),
        // );
      } catch (error) {
        console.error(error);
      }
    },
    [currentChatRecord, messages],
  );

  const startNewChat = useCallback(async () => {
    // No need if there are no messages, we'll just keep the current chat
    // and update the timestamps
    if (messages.length === 0) {
      setCurrentChatRecord({
        ...currentChatRecord,
        createdAt: Date.now(),
        updatedAt: Date.now(),
      });

      return;
    }

    const newChatRecord = {
      id: crypto.randomUUID(),
      createdAt: Date.now(),
      updatedAt: Date.now(),
      preview: "",
    };

    setCurrentChatRecord(newChatRecord);
    setChatRecords((prevChatRecords) => ({
      ...prevChatRecords,
      [newChatRecord.id]: newChatRecord,
    }));
    setMessages([]);
  }, [currentChatRecord, messages]);

  // Backend handles model loading
  // const loadModel = useCallback(
  //   async (initialPrompts: LanguageModelPrompt[] = []) => {
  //     setIsModelLoaded(false);

  //     const options: LanguageModelCreateOptions = {
  //       modelAlias: settings.selectedModel,
  //       systemPrompt: getSystemPrompt(),
  //       topK: settings.topK,
  //       temperature: settings.temperature,
  //       initialPrompts,
  //     };

  //     console.log("Loading model with options:", options);

  //     try {
  //       await electronAi.create(options);
  //       setIsModelLoaded(true);
  //     } catch (error) {
  //       console.error(error);

  //       addMessage({
  //         id: crypto.randomUUID(),
  //         children: <ErrorLoadModelMessageContent error={error} />,
  //         sender: "klippy",
  //         createdAt: Date.now(),
  //       });
  //     }
  //   },
  //   [
  //     settings.selectedModel,
  //     settings.systemPrompt,
  //     settings.topK,
  //     settings.temperature,
  //     messages,
  //   ],
  // );

  const deleteChat = useCallback(
    async (chatId: string) => {
      await klippyApi.deleteChat(chatId);

      setChatRecords((prevChatRecords) => {
        const newChatRecords = { ...prevChatRecords };
        delete newChatRecords[chatId];
        return newChatRecords;
      });

      if (currentChatRecord.id === chatId) {
        await startNewChat();
      }
    },
    [currentChatRecord.id],
  );

  const deleteAllChats = useCallback(async () => {
    await klippyApi.deleteAllChats();

    setChatRecords({});
    setMessages([]);
    startNewChat();
  }, []);

  // Update the chat record in the database whenever messages change
  useEffect(() => {
    const updatedChatRecord = {
      ...currentChatRecord,
      updatedAt: Date.now(),
      preview: currentChatRecord.preview || getPreviewFromMessages(messages),
    };

    const chatWithMessages = {
      chat: updatedChatRecord,
      messages: messages.map(messageRecordFromMessage),
    };

    setCurrentChatRecord(updatedChatRecord);

    klippyApi.writeChatWithMessages(chatWithMessages).catch((error: unknown) => {
      console.error(error);
    });
  }, [messages]);

  // Model loading is handled by backend, no need to load on frontend
  // Load the model when the selected model changes
  // or when the system prompt, topK, or temperature change
  // useEffect(() => {
  //   if (debug?.simulateDownload) {
  //     setIsModelLoaded(true);
  //     return;
  //   }

  //   if (settings.selectedModel) {
  //     loadModel();
  //   } else if (!settings.selectedModel && isModelLoaded) {
  //     electronAi
  //       .destroy()
  //       .then(() => {
  //         setIsModelLoaded(false);
  //       })
  //       .catch((error: unknown) => {
  //         console.error(error);
  //       });
  //   }
  // }, [
  //   settings.selectedModel,
  //   settings.systemPrompt,
  //   settings.topK,
  //   settings.temperature,
  // ]);

  // Backend handles model selection, no need to manage on frontend
  // If selectedModel is undefined or not available, set it to the first downloaded model
  // useEffect(() => {
  //   if (
  //     !settings.selectedModel ||
  //     !models[settings.selectedModel] ||
  //     !models[settings.selectedModel].downloaded
  //   ) {
  //     const downloadedModel = Object.values(models).find(
  //       (model) => model.downloaded,
  //     );

  //     if (downloadedModel) {
  //       klippyApi.setState("settings.selectedModel", downloadedModel.name);
  //     }
  //   }
  // }, [models]);

  // At app startup, initially load the chat records from the main process
  useEffect(() => {
    klippyApi.getChatRecords().then((chatRecords) => {
      setChatRecords(chatRecords);
    });
  }, []);

  // Backend handles models, no need to download on frontend
  // At app startup, check if any models are ready. If none are, kick off a download
  // for our smallest model and tell the user about it.
  // useEffect(() => {
  //   if (
  //     messages.length > 0 ||
  //     Object.keys(models).length === 0 ||
  //     areAnyModelsReadyOrDownloading(models)
  //   ) {
  //     return;
  //   }

  //   if (hasPerformedStartupCheck) {
  //     return;
  //   }

  //   setHasPerformedStartupCheck(true);

  //   addMessage({
  //     id: crypto.randomUUID(),
  //     children: <WelcomeMessageContent />,
  //     content: "Welcome to Klippy!",
  //     sender: "klippy",
  //     createdAt: Date.now(),
  //   });

  //   const downloadModelIfNoneReady = async () => {
  //     await klippyApi.downloadModelByName("Gemma 3 (1B)");

  //     setTimeout(async () => {
  //       await klippyApi.updateModelState();
  //     }, 500);
  //   };

  //   void downloadModelIfNoneReady();
  // }, [models]);

  // Subscribe to the main process's newChat event
  useEffect(() => {
    klippyApi.offNewChat();
    klippyApi.onNewChat(async () => {
      await startNewChat();
    });

    return () => {
      klippyApi.offNewChat();
    };
  }, [startNewChat]);

  const value = {
    chatRecords,
    currentChatRecord,
    selectChat,
    deleteChat,
    deleteAllChats,
    startNewChat,
    messages,
    addMessage,
    setMessages,
    animationKey,
    setAnimationKey,
    status,
    setStatus,
    isModelLoaded,
    isChatWindowOpen,
    setIsChatWindowOpen,
  };

  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
}

export function useChat() {
  const context = useContext(ChatContext);

  if (!context) {
    throw new Error("useChat must be used within a ChatProvider");
  }

  return context;
}

function messageRecordFromMessage(message: Message): MessageRecord {
  return {
    id: message.id,
    content: message.content,
    sender: message.sender,
    createdAt: message.createdAt,
  };
}

function getPreviewFromMessages(messages: Message[]): string {
  if (messages.length === 0) {
    return "";
  }

  if (messages[0].sender === "klippy") {
    return "Welcome to Klippy!";
  }

  // Remove newlines and limit to 100 characters
  return messages[0].content.replace(/\n/g, " ").substring(0, 100);
}

// Backend handles prompts
// function messagesToInitialPrompts(messages: Message[]): LanguageModelPrompt[] {
//   return messages.map((message) => ({
//     role:
//       message.sender === "klippy"
//         ? ("assistant" as LanguageModelPromptRole)
//         : ("user" as LanguageModelPromptRole),
//     type: "text" as LanguageModelPromptType,
//     content: message.content || "",
//   }));
// }
