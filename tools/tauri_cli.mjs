import { spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const args = process.argv.slice(2);
const realCli = path.join(root, "node_modules", "@tauri-apps", "cli", "tauri.js");
const command = args[0];
const fullWindowsBuild = command === "build" && args.length === 1 && process.platform === "win32";
const child = command === "dev"
  ? spawn(process.execPath, [path.join(root, "tools", "desktop_dev.mjs"), ...args.slice(1)], {
      cwd: root,
      stdio: "inherit",
      windowsHide: false,
    })
  : fullWindowsBuild
    ? spawn(process.env.ComSpec || "cmd.exe", ["/d", "/c", path.join(root, "build_desktop.cmd")], {
        cwd: root,
        stdio: "inherit",
        windowsHide: false,
      })
  : spawn(process.execPath, [realCli, ...args], {
      cwd: root,
      stdio: "inherit",
      windowsHide: false,
    });

child.on("error", (error) => {
  console.error(`Не удалось запустить Tauri: ${error.message}`);
  process.exitCode = 1;
});
child.on("exit", (code, signal) => {
  if (signal) process.kill(process.pid, signal);
  else process.exitCode = code ?? 1;
});
