export const IpcMessages = {
  // Window messages
  TOGGLE_CHAT_WINDOW: "klippy_toggle_chat_window",
  MINIMIZE_CHAT_WINDOW: "klippy_minimize_chat_window",
  MAXIMIZE_CHAT_WINDOW: "klippy_maximize_chat_window",
  SET_BUBBLE_VIEW: "klippy_set_bubble_view",
  POPUP_APP_MENU: "klippy_popup_app_menu",

  // Model messages
  DOWNLOAD_MODEL_BY_NAME: "klippy_download_model_by_name",
  REMOVE_MODEL_BY_NAME: "klippy_remove_model_by_name",
  DELETE_MODEL_BY_NAME: "klippy_delete_model_by_name",
  DELETE_ALL_MODELS: "klippy_delete_all_models",
  ADD_MODEL_FROM_FILE: "klippy_add_model_from_file",

  // State messages
  STATE_UPDATE_MODEL_STATE: "klippy_state_update_model_state",
  STATE_CHANGED: "klippy_state_changed",
  STATE_GET_FULL: "klippy_state_get_full",
  STATE_GET: "klippy_state_get",
  STATE_SET: "klippy_state_set",
  STATE_OPEN_IN_EDITOR: "klippy_state_open_in_editor",

  // Debug messages
  DEBUG_STATE_GET_FULL: "klippy_debug_state_get_full",
  DEBUG_STATE_GET: "klippy_debug_state_get",
  DEBUG_STATE_SET: "klippy_debug_state_set",
  DEBUG_STATE_CHANGED: "klippy_debug_state_changed",
  DEBUG_STATE_OPEN_IN_EDITOR: "klippy_debug_state_open_in_editor",
  DEBUG_GET_DEBUG_INFO: "klippy_debug_get_debug_info",

  // App messages
  APP_CHECK_FOR_UPDATES: "klippy_app_check_for_updates",
  APP_GET_VERSIONS: "klippy_app__get_versions",

  // Chat messages
  CHAT_GET_CHAT_RECORDS: "klippy_chat_get_chat_records",
  CHAT_GET_CHAT_WITH_MESSAGES: "klippy_chat_get_chat_with_messages",
  CHAT_WRITE_CHAT_WITH_MESSAGES: "klippy_chat_write_chat_with_messages",
  CHAT_DELETE_CHAT: "klippy_chat_delete_chat",
  CHAT_DELETE_ALL_CHATS: "klippy_chat_delete_all_chats",
  CHAT_NEW_CHAT: "klippy_chat_new_chat",

  // Clipboard
  CLIPBOARD_WRITE: "klippy_clipboard_write",
};
