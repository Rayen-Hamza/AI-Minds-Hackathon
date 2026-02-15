import { app, Tray, Menu, nativeImage } from "electron";
import path from "path";
import { getMainWindow, toggleChatWindow } from "./windows";
import { getLogger } from "./logger";
import { getStateManager } from "./state";
import { IpcMessages } from "../ipc-messages";

let tray: Tray | null = null;

/**
 * Create and setup the system tray
 */
export function setupTray(): void {
  if (tray && !tray.isDestroyed()) {
    getLogger().info("Tray already exists, skipping creation");
    return;
  }

  try {
    const iconPath = getTrayIconPath();
    const icon = nativeImage.createFromPath(iconPath);
    
    tray = new Tray(icon);
    tray.setToolTip("Klippy - Your AI Assistant");
    
    updateTrayMenu();
    
    // Double-click to show/hide main window
    tray.on("double-click", () => {
      toggleMainWindowVisibility();
    });
    
    // Single click behavior (platform specific)
    if (process.platform === "win32") {
      tray.on("click", () => {
        toggleMainWindowVisibility();
      });
    }
    
    getLogger().info("System tray created successfully");
  } catch (error) {
    getLogger().error("Failed to create system tray:", error);
  }
}

/**
 * Get the appropriate tray icon path based on the platform
 */
function getTrayIconPath(): string {
  const isDev = process.env.NODE_ENV === "development";
  
  if (process.platform === "darwin") {
    // macOS uses template images for tray icons
    return path.join(
      isDev ? process.cwd() : process.resourcesPath,
      "assets",
      "icon.icns"
    );
  } else if (process.platform === "win32") {
    return path.join(
      isDev ? process.cwd() : process.resourcesPath,
      "assets",
      "icon.ico"
    );
  } else {
    // Linux
    return path.join(
      isDev ? process.cwd() : process.resourcesPath,
      "assets",
      "icon.png"
    );
  }
}

/**
 * Update the tray context menu
 */
export function updateTrayMenu(): void {
  if (!tray || tray.isDestroyed()) {
    return;
  }

  const mainWindow = getMainWindow();
  const isVisible = mainWindow?.isVisible() ?? false;

  const contextMenu = Menu.buildFromTemplate([
    {
      label: isVisible ? "Hide Klippy" : "Show Klippy",
      click: () => toggleMainWindowVisibility(),
    },
    {
      label: "Toggle Chat Window",
      click: () => toggleChatWindow(),
      accelerator: "Cmd+`",
    },
    { type: "separator" },
    {
      label: "New Chat",
      click: () => {
        mainWindow?.webContents.send(IpcMessages.CHAT_NEW_CHAT);
      },
      accelerator: "CmdOrCtrl+N",
    },
    { type: "separator" },
    {
      label: "Settings",
      click: () => {
        showMainWindow();
        mainWindow?.webContents.send(IpcMessages.SET_BUBBLE_VIEW, "settings-appearance");
      },
    },
    { type: "separator" },
    {
      label: "Quit Klippy",
      click: () => {
        app.quit();
      },
      accelerator: "CmdOrCtrl+Q",
    },
  ]);

  tray.setContextMenu(contextMenu);
}

/**
 * Toggle main window visibility
 */
function toggleMainWindowVisibility(): void {
  const mainWindow = getMainWindow();
  
  if (!mainWindow) {
    return;
  }

  if (mainWindow.isVisible()) {
    mainWindow.hide();
  } else {
    showMainWindow();
  }
  
  updateTrayMenu();
}

/**
 * Show the main window
 */
function showMainWindow(): void {
  const mainWindow = getMainWindow();
  
  if (!mainWindow) {
    return;
  }

  mainWindow.show();
  mainWindow.focus();
  
  // Restore from minimized state if needed
  if (mainWindow.isMinimized()) {
    mainWindow.restore();
  }
  
  updateTrayMenu();
}

/**
 * Hide the main window to tray
 */
export function hideToTray(): void {
  const mainWindow = getMainWindow();
  
  if (mainWindow) {
    mainWindow.hide();
    updateTrayMenu();
  }
}

/**
 * Get the tray instance
 */
export function getTray(): Tray | null {
  return tray;
}

/**
 * Destroy the tray
 */
export function destroyTray(): void {
  if (tray && !tray.isDestroyed()) {
    tray.destroy();
    tray = null;
    getLogger().info("System tray destroyed");
  }
}

/**
 * Check if minimize to tray is enabled
 */
export function isMinimizeToTrayEnabled(): boolean {
  return getStateManager().store.get("settings")?.minimizeToTray ?? false;
}
