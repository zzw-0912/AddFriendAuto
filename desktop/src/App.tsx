import { useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import "./App.css";

function App() {
  const [healthStatus, setHealthStatus] = useState<string>("");
  const [scriptOutput, setScriptOutput] = useState<string[]>([]);
  const [isRunning, setIsRunning] = useState(false);

  const checkHealth = async () => {
    try {
      const res = await fetch("http://127.0.0.1:8000/health");
      const data = await res.json();
      setHealthStatus(JSON.stringify(data));
    } catch {
      setHealthStatus("Server unreachable");
    }
  };

  const runTestScript = async () => {
    setIsRunning(true);
    setScriptOutput([]);
    try {
      const result = await invoke<string>("run_python_script", {
        runId: "tauri_test_001",
      });
      const lines = result.split("\n").filter(Boolean);
      setScriptOutput(lines.map((l) => {
        try {
          return JSON.stringify(JSON.parse(l), null, 2);
        } catch {
          return l;
        }
      }));
    } catch (e: any) {
      setScriptOutput([`Error: ${e}`]);
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <div className="container">
      <h1>FriendAuto</h1>

      <section className="card">
        <h2>Backend Health Check</h2>
        <button onClick={checkHealth}>Check Health</button>
        {healthStatus && <pre className="output">{healthStatus}</pre>}
      </section>

      <section className="card">
        <h2>Test Automation Script</h2>
        <button onClick={runTestScript} disabled={isRunning}>
          {isRunning ? "Running..." : "Run Test Script"}
        </button>
        <div className="log">
          {scriptOutput.map((line, i) => (
            <pre key={i}>{line}</pre>
          ))}
        </div>
      </section>
    </div>
  );
}

export default App;
