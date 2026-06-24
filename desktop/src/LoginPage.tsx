import { useState } from "react";

interface Props {
  apiBase: string;
  machineCode: string;
  onLogin: (token: string, email: string) => void;
}

function LoginPage({ apiBase, machineCode, onLogin }: Props) {
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [codeSent, setCodeSent] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const sendCode = async () => {
    if (!email) return;
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${apiBase}/auth/send-code`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail || "Failed to send code");
      } else {
        setCodeSent(true);
      }
    } catch {
      setError("Cannot reach server");
    } finally {
      setLoading(false);
    }
  };

  const login = async () => {
    if (!email || !code) return;
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${apiBase}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, code, machine_code: machineCode }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail || "Login failed");
      } else {
        onLogin(data.access_token, email);
      }
    } catch {
      setError("Cannot reach server");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container login-container">
      <h1>FriendAuto</h1>
      <div className="card">
        <h2>Login</h2>
        <p className="hint">Enter your email to receive a verification code</p>
        <input
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          disabled={codeSent}
        />
        {!codeSent ? (
          <button onClick={sendCode} disabled={loading || !email}>
            {loading ? "Sending..." : "Send Code"}
          </button>
        ) : (
          <>
            <input
              type="text"
              placeholder="Verification code"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              maxLength={6}
            />
            <button onClick={login} disabled={loading || code.length < 6}>
              {loading ? "Logging in..." : "Login"}
            </button>
            <button className="link" onClick={() => setCodeSent(false)}>
              Change email
            </button>
          </>
        )}
        {error && <p className="error">{error}</p>}
      </div>
    </div>
  );
}

export default LoginPage;
