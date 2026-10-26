import { readFileSync, unlinkSync, writeFileSync } from "node:fs";
import { spawn, spawnSync } from "node:child_process";
import net from "node:net";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const configPath = path.join(root, "src-tauri", "tauri.dev.generated.json");
const pythonPath = path.join(root, ".venv", "Scripts", "python.exe");
const isWindows = process.platform === "win32";

function freePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const port = server.address().port;
      server.close(() => resolve(port));
    });
  });
}

function portIsOpen(port) {
  return new Promise((resolve) => {
    const socket = net.createConnection({ host: "127.0.0.1", port });
    socket.once("connect", () => { socket.destroy(); resolve(true); });
    socket.once("error", () => { socket.destroy(); resolve(false); });
  });
}

async function waitForBackend(port, child) {
  const deadline = Date.now() + 30_000;
  while (Date.now() < deadline) {
    if (child.exitCode !== null || child.signalCode) throw new Error("Backend завершился до запуска.");
    if (await portIsOpen(port)) return;
    await new Promise((resolve) => setTimeout(resolve, 150));
  }
  throw new Error(`Backend не открыл порт ${port} за 30 секунд.`);
}

function stopProcess(child) {
  if (!child || child.exitCode !== null) return;
  if (isWindows) {
    spawnSync("taskkill", ["/pid", String(child.pid), "/t", "/f"], { stdio: "ignore" });
  } else {
    child.kill("SIGTERM");
  }
}

let backend;
let tauri;
let cleaned = false;
function cleanup(code = 0) {
  if (cleaned) return;
  cleaned = true;
  stopProcess(tauri);
  stopProcess(backend);
  try { unlinkSync(configPath); } catch {}
  process.exitCode = code;
}

try {
  const port = await freePort();
  const config = JSON.parse(readFileSync(path.join(root, "src-tauri", "tauri.conf.json"), "utf8"));
  config.build.devUrl = `http://127.0.0.1:${port}`;
  delete config.build.beforeDevCommand;
  // The dev backend is started above by this script. Bundled resources are
  // only produced by build_desktop.cmd and must not block `tauri dev`.
  config.bundle = { ...(config.bundle || {}), resources: [] };
  writeFileSync(configPath, JSON.stringify(config, null, 2), "utf8");

  backend = spawn(pythonPath, ["desktop_runner.py", "--host", "127.0.0.1", "--port", String(port)], {
    cwd: root,
    env: { ...process.env, VOICEBRIDGE_PORT: String(port) },
    stdio: "inherit",
    windowsHide: true,
  });
  backend.once("error", (error) => {
    console.error(`Не удалось запустить backend: ${error.message}`);
    cleanup(1);
  });

  await waitForBackend(port, backend);
  console.log(`Voice Bridge dev backend: http://127.0.0.1:${port}`);
  tauri = spawn(process.execPath, [
    path.join(root, "node_modules", "@tauri-apps", "cli", "tauri.js"),
    "dev",
    "--config",
    configPath,
  ], {
    cwd: root,
    env: process.env,
    stdio: "inherit",
    windowsHide: false,
  });
  tauri.once("exit", (code) => cleanup(code || 0));
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  cleanup(1);
}

process.once("SIGINT", () => cleanup(0));
process.once("SIGTERM", () => cleanup(0));
