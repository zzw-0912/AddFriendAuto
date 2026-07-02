export type TargetType = "contact" | "phone" | "wechat_id";

export interface TaskDefaults {
  targetType: TargetType;
  dailyLimit: number;
  createTag: boolean;
  greetingText: string;
  greetingPresets: string[];
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
  greetingPresets: [
    "你好，很高兴认识你，方便加个微信交流一下吗？",
    "您好，看到您的资料很不错，想加个好友认识一下。",
    "你好，我这边想和你交流一下相关信息，方便通过好友吗？",
  ],
};

export interface UserStatus {
  membership: { is_active: boolean; plan_id: number | null; ends_at: string | null };
  trial: { total: number; used: number; remaining: number };
}
