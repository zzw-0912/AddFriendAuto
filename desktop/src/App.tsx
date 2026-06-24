import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import LoginPage from "./LoginPage";
import MainPage from "./MainPage";
import "./App.css";

const API_BASE = "http://127.0.0.1:8001";

interface StoredAuth {
  token: string;
  email: string;
}

function App() {
  const [auth, setAuth] = useState<StoredAuth | null>(null);
  const [loading, setLoading] = useState(true);
  const [machineCode, setMachineCode] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const mc = await invoke<string>("get_machine_code");
        setMachineCode(mc);
      } catch {
        setMachineCode("unknown");
      }
      try {
        const stored = await invoke<StoredAuth | null>("load_token");
        if (stored?.token) {
          setAuth(stored);
        }
      } catch {
        // no saved token
      }
      setLoading(false);
    })();
  }, []);

  const handleLogin = (token: string, email: string) => {
    const authData = { token, email };
    setAuth(authData);
    invoke("save_token", { token, email });
  };

  const handleLogout = () => {
    setAuth(null);
    invoke("clear_token");
  };

  if (loading) {
    return <div className="container"><p>Loading...</p></div>;
  }

  if (!auth) {
    return <LoginPage apiBase={API_BASE} machineCode={machineCode} onLogin={handleLogin} />;
  }

  return <MainPage apiBase={API_BASE} auth={auth} machineCode={machineCode} onLogout={handleLogout} />;
}

export default App;
