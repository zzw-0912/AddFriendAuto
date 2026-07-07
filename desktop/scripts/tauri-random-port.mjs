import { spawn } from "node:child_process";
import net from "node:net";
import path from "node:path";
import { fileURLToPath } from "node:url";

function findFreePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.unref();
    server.on("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      const port = typeof address === "object" && address ? address.port : 0;
      server.close(() => resolve(port));
    });
  });
}

function run(command, args, options = {}) {
  const child = spawn(command, args, {
    stdio: "inherit",
    shell: false,
    ...options,
  });

  child.on("exit", (code, signal) => {
    if (signal) {
      process.kill(process.pid, signal);
      return;
    }
    process.exit(code ?? 0);
  });
}

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const desktopRoot = path.resolve(scriptDir, "..");
const tauriCli = path.join(desktopRoot, "node_modules", "@tauri-apps", "cli", "tauri.js");
const args = process.argv.slice(2);
const [command, ...rest] = args;

if (command !== "dev") {
  run(process.execPath, [tauriCli, ...args], { cwd: desktopRoot });
} else {
  const port = await findFreePort();
  const devUrl = `http://localhost:${port}`;
  const config = {
    build: {
      devUrl,
      beforeDevCommand: `npm run dev -- --host 127.0.0.1 --port ${port} --strictPort`,
    },
  };

  console.log(`[FriendAuto] Tauri dev server port: ${port}`);
  run(process.execPath, [tauriCli, "dev", "--config", JSON.stringify(config), ...rest], {
    cwd: desktopRoot,
    env: {
      ...process.env,
      VITE_DEV_PORT: String(port),
    },
  });
}
