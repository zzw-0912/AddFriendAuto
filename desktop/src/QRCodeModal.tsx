interface Props {
  visible: boolean;
  onClose: () => void;
  qrImages?: (string | undefined)[];
  orderInfo?: {
    orderNo: string;
    planName: string;
    amountYuan: number;
    userEmail: string;
  } | null;
}

function QRCodeModal({ visible, onClose, qrImages = [undefined, undefined], orderInfo = null }: Props) {
  return (
    <div className={`modal-overlay qr-overlay${visible ? " show" : ""}`} onClick={onClose}>
      <div className="modal-box qr-modal-box" onClick={(e) => e.stopPropagation()}>
        <div className="modal-icon">
          <svg viewBox="0 0 24 24" fill="currentColor">
            <path d="M8.691 2.188C3.891 2.188 0 5.476 0 9.53c0 2.212 1.17 4.203 3.002 5.55a.59.59 0 0 1 .213.665l-.39 1.48c-.019.07-.048.141-.048.213 0 .163.13.295.29.295a.326.326 0 0 0 .167-.054l1.903-1.114a.864.864 0 0 1 .717-.098 10.16 10.16 0 0 0 2.837.403c.276 0 .543-.027.811-.05-.857-2.578.157-4.972 1.932-6.446 1.703-1.415 3.882-1.98 5.853-1.838-.576-3.583-4.196-6.348-8.596-6.348zM5.785 5.991c.642 0 1.162.529 1.162 1.18a1.17 1.17 0 0 1-1.162 1.178A1.17 1.17 0 0 1 4.623 7.17c0-.651.52-1.18 1.162-1.18zm5.813 0c.642 0 1.162.529 1.162 1.18a1.17 1.17 0 0 1-1.162 1.178 1.17 1.17 0 0 1-1.162-1.178c0-.651.52-1.18 1.162-1.18zm5.34 2.867c-1.797-.052-3.746.512-5.28 1.786-1.72 1.428-2.687 3.72-1.78 6.22.942 2.453 3.666 4.229 6.884 4.229.826 0 1.622-.12 2.361-.336a.722.722 0 0 1 .598.082l1.584.926a.272.272 0 0 0 .14.045c.134 0 .24-.11.24-.245 0-.06-.024-.12-.04-.178l-.325-1.233a.492.492 0 0 1 .178-.554C23.028 18.48 24 16.82 24 14.98c0-3.21-2.931-5.952-7.062-6.122zm-2.18 2.769c.535 0 .969.44.969.982a.976.976 0 0 1-.969.983.976.976 0 0 1-.969-.983c0-.542.434-.982.97-.982zm4.844 0c.535 0 .969.44.969.982a.976.976 0 0 1-.969.983.976.976 0 0 1-.969-.983c0-.542.434-.982.97-.982z" />
          </svg>
        </div>
        <h3>扫码添加工作人员</h3>
        <p className="modal-sub">添加好友后，工作人员将为您开通会员</p>
        {orderInfo && (
          <div className="qr-order-card">
            <div>
              <span>订单号</span>
              <strong className="mono">{orderInfo.orderNo}</strong>
            </div>
            <div>
              <span>套餐</span>
              <strong>{orderInfo.planName}</strong>
            </div>
            <div>
              <span>金额</span>
              <strong>¥{orderInfo.amountYuan.toFixed(2)}</strong>
            </div>
            <div>
              <span>账号</span>
              <strong>{orderInfo.userEmail}</strong>
            </div>
          </div>
        )}
        <div className="qr-row">
          {qrImages.map((src, i) => (
            <div key={i} className="qr-item">
              <div className="qr-wrapper">
                {src ? (
                  <img src={src} alt={`微信客服${i + 1}`} className="qr-img" />
                ) : (
                  <div className="qr-placeholder">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <rect x="3" y="3" width="7" height="7" rx="1" />
                      <rect x="14" y="3" width="7" height="7" rx="1" />
                      <rect x="3" y="14" width="7" height="7" rx="1" />
                      <path d="M14 14h2v2h-2zM18 14h2v2h-2zM14 18h2v2h-2zM18 18h2v2h-2z" />
                    </svg>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
        <p className="modal-note">请使用微信扫描二维码添加好友</p>
        <button className="btn-cancel" onClick={onClose}>取消</button>
      </div>
    </div>
  );
}

export default QRCodeModal;
