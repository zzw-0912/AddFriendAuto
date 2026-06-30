export type TargetType = "contact" | "phone" | "wechat_id";

export interface TaskDefaults {
  targetType: TargetType;
  dailyLimit: number;
  createTag: boolean;
  greetingText: string;
}

export interface WeChatWindowInfo {
  hwnd: number;
  pid: number;
  title: string;
  processName: string;
  displayName: string;
}

export interface WeChatWindowBinding {
  slotId: number;
  hwnd: number;
  pid: number;
  title: string;
  displayName: string;
  boundAt: string;
}

export interface AutoDoorConfig {
  autodoorSourcePath: string;
  projectPath: string;
  editorExecutablePath: string;
}

export const TASK_DEFAULTS_STORAGE_KEY = "friendauto.taskDefaults.v1";
export const TASK_SLOT_CONFIGS_STORAGE_KEY = "friendauto.taskSlotConfigs.v1";
export const WECHAT_BINDINGS_STORAGE_KEY = "friendauto.wechatBindings.v1";

export const DEFAULT_TASK_DEFAULTS: TaskDefaults = {
  targetType: "contact",
  dailyLimit: 20,
  createTag: false,
  greetingText: "",
};

export interface UserStatus {
  membership: { is_active: boolean; plan_id: number | null; ends_at: string | null };
  trial: { total: number; used: number; remaining: number };
}
