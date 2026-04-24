"""测试考生认证依赖函数."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi import Depends, FastAPI, status
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.database import get_db
from app.models import Exam, ExamStatus, Student, SubmitStatus
from app.utils.student_auth import create_student_token, require_student


# 创建测试用的 FastAPI 应用
@pytest.fixture
def test_app(db_session):
    """创建测试应用."""
    app = FastAPI()

    # 覆盖数据库依赖
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    @app.get("/test/student")
    async def test_endpoint(student: Student = Depends(require_student)):
        """测试端点，使用 require_student 依赖."""
        return {
            "id": student.id,
            "student_id": student.student_id,
            "name": student.name,
        }

    return app


@pytest.fixture
async def test_client(test_app):
    """创建测试客户端."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
async def exam(db_session):
    """创建测试考试."""
    exam = Exam(
        name="测试考试",
        subject="C语言",
        duration=120,
        start_time=datetime.now(UTC),
        end_time=datetime.now(UTC) + timedelta(hours=2),
        status=ExamStatus.NOT_STARTED,
        pledge_content="测试承诺书",
    )
    db_session.add(exam)
    await db_session.commit()
    await db_session.refresh(exam)
    return exam


@pytest.fixture
async def student(db_session, exam):
    """创建测试考生."""
    student = Student(
        exam_id=exam.id,
        student_id="2024001001",
        name="张三",
        login_code="ABC12345",
        login_code_used=True,
        login_time=datetime.now(UTC),
        submit_status=SubmitStatus.IN_PROGRESS,
    )
    db_session.add(student)
    await db_session.commit()
    await db_session.refresh(student)
    return student


class TestRequireStudent:
    """测试 require_student 依赖函数."""

    async def test_invalid_authorization_header_format(self, test_client):
        """测试无效的 Authorization 头格式（不以 'Bearer ' 开头）."""
        # 测试没有 Bearer 前缀
        response = await test_client.get(
            "/test/student",
            headers={"Authorization": "invalid_token"},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Authorization header missing" in response.json()["detail"]

        # 测试空 Authorization 头
        response = await test_client.get("/test/student")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_expired_or_invalid_jwt_token(self, test_client):
        """测试过期或无效的 JWT Token."""
        # 测试无效的 token
        response = await test_client.get(
            "/test/student",
            headers={"Authorization": "Bearer invalid_token"},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid or expired token" in response.json()["detail"]

        # 测试过期的 token
        expired_payload = {
            "type": "student",
            "student_id": 1,
            "exam_id": 1,
            "exp": datetime.now(UTC) - timedelta(hours=1),  # 已过期
        }
        expired_token = jwt.encode(
            expired_payload, settings.secret_key, algorithm=settings.algorithm
        )
        response = await test_client.get(
            "/test/student",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid or expired token" in response.json()["detail"]

    async def test_non_student_token_type(self, test_client):
        """测试非学生类型的 Token（例如 admin token）."""
        # 创建 admin 类型的 token
        admin_payload = {
            "type": "admin",  # 非 student 类型
            "admin_id": 1,
            "exp": datetime.now(UTC) + timedelta(hours=1),
        }
        admin_token = jwt.encode(admin_payload, settings.secret_key, algorithm=settings.algorithm)
        response = await test_client.get(
            "/test/student",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid token type" in response.json()["detail"]

        # 测试缺少 type 字段的 token
        no_type_payload = {
            "student_id": 1,
            "exam_id": 1,
            "exp": datetime.now(UTC) + timedelta(hours=1),
        }
        no_type_token = jwt.encode(
            no_type_payload, settings.secret_key, algorithm=settings.algorithm
        )
        response = await test_client.get(
            "/test/student",
            headers={"Authorization": f"Bearer {no_type_token}"},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid token type" in response.json()["detail"]

    async def test_payload_missing_student_id(self, test_client):
        """测试 Payload 中缺少 student_id."""
        # 创建缺少 student_id 的 token
        payload = {
            "type": "student",
            # 缺少 student_id
            "exam_id": 1,
            "exp": datetime.now(UTC) + timedelta(hours=1),
        }
        token = jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)
        response = await test_client.get(
            "/test/student",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid token payload" in response.json()["detail"]

    async def test_student_not_found(self, test_client):
        """测试学生不存在于数据库中."""
        # 创建一个有效的 token，但对应的学生 ID 不存在
        non_existent_student_id = 99999
        token = create_student_token(non_existent_student_id, exam_id=1)

        response = await test_client.get(
            "/test/student",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Student not found" in response.json()["detail"]

    async def test_valid_student_token(self, test_client, student, db_session):
        """测试有效的学生 Token（成功场景）."""
        # 创建有效的学生 token
        token = create_student_token(student.id, student.exam_id)

        response = await test_client.get(
            "/test/student",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == student.id
        assert data["student_id"] == student.student_id
        assert data["name"] == student.name


class TestCreateStudentToken:
    """测试 create_student_token 函数."""

    def test_create_token_structure(self):
        """测试创建的 token 结构正确."""
        token = create_student_token(student_id=1, exam_id=2)

        # 解码 token 验证内容
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])

        assert payload["type"] == "student"
        assert payload["student_id"] == 1
        assert payload["exam_id"] == 2
        assert "exp" in payload

    def test_token_expiration(self):
        """测试 token 包含正确的过期时间."""
        before_create = datetime.now(UTC)
        token = create_student_token(student_id=1, exam_id=2)
        after_create = datetime.now(UTC)

        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        exp_timestamp = payload["exp"]
        exp_datetime = datetime.fromtimestamp(exp_timestamp, UTC)

        expected_exp_minutes = settings.access_token_expire_minutes
        min_expected = before_create + timedelta(minutes=expected_exp_minutes - 1)
        max_expected = after_create + timedelta(minutes=expected_exp_minutes + 1)

        assert min_expected <= exp_datetime <= max_expected
