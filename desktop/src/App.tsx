import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import LoginPage from "./LoginPage";
import MainPage from "./MainPage";
import { saveAccount } from "./api";
import "./App.css";

const API_BASE = (import.meta.env.VITE_API_BASE || "http://127.0.0.1:8001").replace(/\/$/, "");

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
          const res = await fetch(`${API_BASE}/me/status`, {
            headers: { Authorization: `Bearer ${stored.token}` },
          });
          if (res.ok) {
            setAuth(stored);
          } else if (res.status === 401 || res.status === 403) {
            await invoke("clear_token");
          }
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
    saveAccount(email, token);
  };

  const handleSwitchAccount = (token: string, email: string) => {
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

  return <MainPage apiBase={API_BASE} auth={auth} machineCode={machineCode} onLogout={handleLogout} onSwitchAccount={handleSwitchAccount} />;
}

export default App;
