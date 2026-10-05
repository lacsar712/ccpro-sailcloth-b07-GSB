"""本地/CI 测试设置：用内存 SQLite 代替 Postgres，无需起数据库容器。"""

from .settings import *  # noqa: F401,F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}
