# FriendAuto MySQL 迁移说明

适用场景：从当前 `server/friendauto.db` 的 SQLite 数据迁移到 MySQL，并保留现有数据。

## 推荐版本

- 生产推荐 MySQL `8.4 LTS`。
- 字符集使用 `utf8mb4`，确保中文、微信昵称和 emoji 能正常保存。
- 如果数据库和 API 在同一台服务器，`DATABASE_URL` 里的主机用 `127.0.0.1`；如果数据库在另一台阿里云服务器，优先用内网 IP，不建议直接开放公网数据库端口。

## 初始化 MySQL

```sql
CREATE DATABASE friendauto CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE USER 'friendauto'@'127.0.0.1' IDENTIFIED BY 'replace-with-strong-password';
GRANT ALL PRIVILEGES ON friendauto.* TO 'friendauto'@'127.0.0.1';
FLUSH PRIVILEGES;
```

生产环境 `server/.env` 示例：

```env
DATABASE_URL=mysql+pymysql://friendauto:replace-with-strong-password@127.0.0.1:3306/friendauto?charset=utf8mb4
DEBUG=false
```

## 迁移步骤

1. 停止 API 服务，确保迁移期间没有新写入。
2. 备份 `server/friendauto.db` 和 `server/uploads/`。
3. 安装依赖并在空 MySQL 库中建表。不要对源 SQLite 文件执行这一步：

```bash
cd /opt/FriendAuto/server
source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH="$PWD"
export DATABASE_URL="mysql+pymysql://friendauto:replace-with-strong-password@127.0.0.1:3306/friendauto?charset=utf8mb4"
python -m alembic upgrade head
```

4. 在项目根目录预演数据迁移：

```bash
cd /opt/FriendAuto
python scripts/migrate_sqlite_to_mysql.py --mysql-url "$DATABASE_URL" --dry-run
```

5. 确认行数正常后执行正式迁移：

```bash
python scripts/migrate_sqlite_to_mysql.py --mysql-url "$DATABASE_URL"
```

6. 启动或重启 API 服务，并检查：

```bash
curl http://127.0.0.1:8001/health
```

## 注意事项

- 不要在启动 API 后再迁移数据；API 启动会初始化套餐和管理员，目标 MySQL 就不再是空库。
- 如果迁移脚本提示目标表已有数据，先确认备份，再决定是否使用 `--truncate-target`。
- `task_results` 中同一任务、同一联系人重复上报的数据会保留最早一条，后续重复行会跳过。
- 迁移完成后保留 SQLite 备份，至少覆盖一个发布周期。
- 正式切换前建议用一份 SQLite 副本在测试 MySQL 上完整演练一次。
