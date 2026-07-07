const EXACT_MESSAGES: Record<string, string> = {
  "please wait 60 seconds before requesting a new code": "请等待 60 秒后再重新获取验证码",
  "account already bound to another device. contact admin to unbind.": "该账号已绑定其他设备，请联系管理员解绑",
  "account already bound to another device": "该账号已绑定其他设备，请联系管理员解绑",
  "account does not exist": "账号不存在，请先注册",
  "no password set. please use 'find account' to set your password.": "该账号还未设置密码，请通过找回密码设置新密码",
  "incorrect password": "密码错误，请重新输入",
  "account device binding conflict. please retry.": "设备绑定冲突，请稍后重试",
  "invalid or expired code": "验证码错误或已过期",
  "email already registered": "该邮箱已注册，请直接登录",
  "email already registered or device already bound.": "该邮箱已注册或设备已绑定，请检查后重试",
  "invalid token": "登录状态已失效，请重新登录",
  "user not found or inactive": "账号不存在或已被停用",
  "field required": "请完整填写信息",
};

function detailToText(detail: unknown): string {
  if (!detail) return "";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => detailToText(item))
      .filter(Boolean)
      .join("；");
  }
  if (typeof detail === "object") {
    const value = detail as Record<string, unknown>;
    return detailToText(value.msg || value.message || value.detail);
  }
  return String(detail);
}

export function authErrorMessage(detail: unknown, fallback: string) {
  const raw = detailToText(detail).trim();
  if (!raw) return fallback;

  const exact = EXACT_MESSAGES[raw.toLowerCase()];
  if (exact) return exact;

  const lower = raw.toLowerCase();
  if (lower.includes("valid email") || lower.includes("email address")) return "请输入正确的邮箱地址";
  if (lower.includes("match pattern") || lower.includes("pattern")) return "验证码格式不正确";
  if (lower.includes("at least") || lower.includes("too short")) return "输入内容长度不符合要求";
  if (lower.includes("too many") || lower.includes("rate")) return "操作太频繁，请稍后再试";
  if (lower.includes("device")) return "设备绑定异常，请联系管理员处理";
  if (lower.includes("password")) return "密码错误或格式不正确";
  if (lower.includes("code")) return "验证码错误或已过期";
  if (lower.includes("email")) return "邮箱填写有误，请检查后重试";

  return raw;
}
