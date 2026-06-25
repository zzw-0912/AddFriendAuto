"""
Test automation script for FriendAuto Stage 3.
Reads JSON config from stdin, simulates sending friend requests,
and outputs JSON events line by line to stdout.
"""
import json
import sys
import time


def emit(event: dict):
    print(json.dumps(event, ensure_ascii=False))
    sys.stdout.flush()


def main():
    raw = sys.stdin.read()
    try:
        config = json.loads(raw)
    except json.JSONDecodeError:
        emit({"event": "error", "message": "Invalid JSON config"})
        sys.exit(1)

    run_id = config.get("run_id", "unknown")
    contacts = config.get("contacts", [])
    create_tag = config.get("create_tag", False)
    greeting_text = config.get("greeting_text", "")

    emit({"run_id": run_id, "event": "started", "message": f"开始任务，共 {len(contacts)} 个联系人", "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S+08:00")})

    if not contacts:
        emit({"run_id": run_id, "event": "progress", "message": "没有联系人，生成 3 个测试联系人", "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S+08:00")})
        contacts = [
            {"contact_id": 1001, "wechat_nickname": "张三", "wechat_id": "wxid_zhangsan"},
            {"contact_id": 1002, "wechat_nickname": "李四", "wechat_id": "wxid_lisi"},
            {"contact_id": 1003, "wechat_nickname": "王五", "wechat_id": "wxid_wangwu"},
        ]

    for i, contact in enumerate(contacts):
        cid = contact.get("contact_id", f"test_{i}")
        nickname = contact.get("wechat_nickname", f"Contact_{i}")

        emit({"run_id": run_id, "contact_id": cid, "event": "progress", "message": f"正在处理 {nickname}...", "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S+08:00")})
        time.sleep(1.0)

        if i == 1:
            emit({"run_id": run_id, "contact_id": cid, "event": "failed", "message": f"{nickname} 添加失败：找不到该用户", "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S+08:00")})
        else:
            emit({"run_id": run_id, "contact_id": cid, "event": "success", "message": f"{nickname} 添加成功", "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S+08:00")})

    emit({"run_id": run_id, "event": "finished", "message": "任务完成", "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S+08:00")})


if __name__ == "__main__":
    main()
