from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.database import Base
from app.models.user import User
from app.models.email_code import EmailCode
from app.models.device import Device
from app.models.plan import Plan
from app.models.order import Order
from app.models.membership import Membership
from app.models.trial_quota import TrialQuota
from app.models.task import Task
from app.models.task_result import TaskResult
from app.models.contact import Contact
from app.models.admin_user import AdminUser
from app.models.admin_audit_log import AdminAuditLog

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
