import { useEffect, useState } from "react";
import { getVersion } from "@tauri-apps/api/app";
import { invoke } from "@tauri-apps/api/core";
import ForceUpdateModal from "./ForceUpdateModal";
import LoginPage from "./LoginPage";
import MainPage from "./MainPage";
import { FALLBACK_CLIENT_VERSION, installClientUpdateInterceptor, saveAccount, type ClientUpdateRequiredPayload } from "./api";
import "./App.css";

const API_BASE = (import.meta.env.VITE_API_BASE || "http://47.111.3.83:8001").replace(/\/$/, "");

interface StoredAuth {
  token: string;
  email: string;
}

function App() {
  const [auth, setAuth] = useState<StoredAuth | null>(null);
  const [loading, setLoading] = useState(true);
  const [machineCode, setMachineCode] = useState("");
  const [clientVersion, setClientVersion] = useState(FALLBACK_CLIENT_VERSION);
  const [updateRequired, setUpdateRequired] = useState<ClientUpdateRequiredPayload | null>(null);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      let detectedVersion = FALLBACK_CLIENT_VERSION;
      try {
        detectedVersion = await getVersion();
      } catch {
        detectedVersion = FALLBACK_CLIENT_VERSION;
      }
      if (cancelled) return;
      setClientVersion(detectedVersion);
      installClientUpdateInterceptor(API_BASE, detectedVersion, (payload) => setUpdateRequired(payload));

      try {
        const mc = await invoke<string>("get_machine_code");
        if (cancelled) return;
        setMachineCode(mc);
      } catch {
        if (cancelled) return;
        setMachineCode("unknown");
      }
      try {
        const stored = await invoke<StoredAuth | null>("load_token");
        if (stored?.token) {
          const res = await fetch(`${API_BASE}/me/status`, {
            headers: { Authorization: `Bearer ${stored.token}` },
          });
          if (res.ok) {
            if (cancelled) return;
            setAuth(stored);
          } else if (res.status === 401 || res.status === 403) {
            await invoke("clear_token");
          }
        }
      } catch {
        // no saved token
      }
      if (cancelled) return;
      setLoading(false);
    })();

    return () => {
      cancelled = true;
    };
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

  const forceUpdateModal = updateRequired ? (
    <ForceUpdateModal apiBase={API_BASE} clientVersion={clientVersion} update={updateRequired} />
  ) : null;

  if (!auth) {
    if (loading) {
      return (
        <>
          <div className="container"><p>加载中...</p></div>
          {forceUpdateModal}
        </>
      );
    }

    return (
      <>
        <LoginPage apiBase={API_BASE} machineCode={machineCode} onLogin={handleLogin} />
        {forceUpdateModal}
      </>
    );
  }

  return (
    <>
      <MainPage apiBase={API_BASE} auth={auth} machineCode={machineCode} onLogout={handleLogout} onSwitchAccount={handleSwitchAccount} />
      {forceUpdateModal}
    </>
  );
}

export default App;
