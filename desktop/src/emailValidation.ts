export const QQ_EMAIL_ONLY_MESSAGE = "仅支持 QQ 邮箱";

export function normalizeEmail(email: string) {
  return email.trim().toLowerCase();
}

export function isQqEmail(email: string) {
  return /^[^\s@]+@qq\.com$/i.test(normalizeEmail(email));
}
