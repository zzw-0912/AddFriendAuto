import { useEffect, useState } from "react";

let _isOnline = navigator.onLine;
const listeners = new Set<(online: boolean) => void>();

function notify(online: boolean) {
  _isOnline = online;
  listeners.forEach((fn) => fn(online));
}

window.addEventListener("online", () => notify(true));
window.addEventListener("offline", () => notify(false));

export function useNetworkStatus() {
  const [isOnline, setIsOnline] = useState(_isOnline);

  useEffect(() => {
    const handler = (online: boolean) => setIsOnline(online);
    listeners.add(handler);
    return () => {
      listeners.delete(handler);
    };
  }, []);

  return { isOnline, isOffline: !isOnline };
}
