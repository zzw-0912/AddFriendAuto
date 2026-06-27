import { useCallback, useEffect, useRef, useState } from "react";

export function useSendCode(apiBase: string, showToast: (message: string) => void) {
  const [countdown, setCountdown] = useState(0);
  const timer = useRef<ReturnType<typeof setInterval>>(undefined);

  const send = useCallback(async (email: string) => {
    if (!email) {
      showToast("请先输入邮箱地址");
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      showToast("请输入有效的邮箱地址");
      return;
    }

    setCountdown(60);
    try {
      const res = await fetch(`${apiBase}/auth/send-code`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      const data = await res.json();
      if (!res.ok) {
        showToast(data.detail || "发送失败");
        setCountdown(0);
        return;
      }
      showToast("验证码已发送");
    } catch {
      showToast("无法连接服务器");
      setCountdown(0);
      return;
    }

    clearInterval(timer.current);
    timer.current = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          clearInterval(timer.current);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
  }, [apiBase, showToast]);

  useEffect(() => () => clearInterval(timer.current), []);

  return { countdown, send };
}
