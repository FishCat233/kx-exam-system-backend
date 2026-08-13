"""SQLAlchemy 枚举列工具."""

import enum


def enum_values(enum_cls: type[enum.Enum]) -> list[str]:
    """生成 Enum 列的 values_callable，使用枚举值而非成员名.

    SQLAlchemy 的 Enum(SomeClass) 默认把枚举成员名（如 SUPER_ADMIN）写入数据库，
    而迁移 DDL 定义的值是小写（如 super_admin）。PostgreSQL 枚举大小写敏感，
    必须用 values_callable 强制使用枚举值，保证模型与迁移一致。
    """
    return [member.value for member in enum_cls]
