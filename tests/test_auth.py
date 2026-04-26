"""认证相关测试."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """测试健康检查端点."""
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient):
    """测试根路径端点."""
    response = await client.get("/")
    assert response.status_code == 200
    assert "message" in response.json()


@pytest.mark.asyncio
async def test_student_login_exam_not_found(client: AsyncClient):
    """测试考生登录端点（考试不存在）."""
    response = await client.post(
        "/api/auth/student/login",
        json={"student_id": "123456", "name": "张三", "login_code": "ABC123", "exam_id": 99999},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_student_login_validation_error(client: AsyncClient):
    """测试考生登录数据验证."""
    # 学号不是纯数字
    response = await client.post(
        "/api/auth/student/login",
        json={"student_id": "abc123", "name": "张三", "login_code": "ABC123", "exam_id": 1},
    )
    assert response.status_code == 422

    # 姓名包含非法字符（既不是中文也不是英文）
    response = await client.post(
        "/api/auth/student/login",
        json={"student_id": "123456", "name": "John@123", "login_code": "ABC123", "exam_id": 1},
    )
    assert response.status_code == 422
