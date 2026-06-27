interface Props {
  isOffline: boolean;
}

function OfflineBanner({ isOffline }: Props) {
  if (!isOffline) return null;

  return (
    <div className="offline-banner" role="alert">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" width="18" height="18">
        <path d="M1 1l22 22" />
        <path d="M16.7 3.5A10.9 10.9 0 0 1 22 12" />
        <path d="M10.8 5.9a7.7 7.7 0 0 1 8.8 3.8" />
        <path d="M5.1 7.5A10.4 10.4 0 0 0 2 12" />
        <path d="M9.1 11.5a4.2 4.2 0 0 1 5.8 0" />
        <path d="M12 20h.01" strokeWidth="2" strokeLinecap="round" />
      </svg>
      <span>网络连接已断开，部分功能暂时不可用</span>
    </div>
  );
}

export default OfflineBanner;
