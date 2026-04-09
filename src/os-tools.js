import { spawn } from "node:child_process";
import { z } from "zod";
import { formatTextResult } from "./tool-utils.js";

function openSteamUri(steamUri) {
  return new Promise((resolve, reject) => {
    const child = spawn("powershell", ["-NoProfile", "-Command", `Start-Process '${steamUri}'`], {
      stdio: "ignore",
      detached: false
    });

    child.on("error", reject);
    child.on("exit", (code) => {
      if (code === 0) {
        resolve();
        return;
      }

      reject(new Error(`Steam launcher exited with code ${code}`));
    });
  });
}

export function registerOsTools(server) {
  server.tool(
    "open_steam",
    "Open the Steam desktop app on Windows.",
    {},
    async () => {
      if (process.platform !== "win32") {
        throw new Error("open_steam currently supports Windows only.");
      }

      await openSteamUri("steam:");
      return formatTextResult("Steam launch command sent.");
    }
  );

  server.tool(
    "open_steam_game",
    "Open a Steam game by app id on Windows.",
    {
      app_id: z.union([z.string().min(1), z.number().int().positive()])
    },
    async ({ app_id }) => {
      if (process.platform !== "win32") {
        throw new Error("open_steam_game currently supports Windows only.");
      }

      await openSteamUri(`steam://run/${String(app_id)}`);
      return formatTextResult(`Steam game launch command sent for app id ${String(app_id)}.`);
    }
  );
}
