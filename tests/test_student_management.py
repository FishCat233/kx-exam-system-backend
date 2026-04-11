"""学生管理和操作相关测试."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models import (
    AdminToken,
    Exam,
    ExamStatus,
    OperationLevel,
    OperationLog,
    Problem,
    Student,
    SubmitStatus,
)
from app.utils import create_access_token, generate_login_code


@pytest.fixture
async def admin_token(db_session) -> AdminToken:
    """创建管理员 Token."""
    token_payload = {"type": "admin"}
    jwt_token = create_access_token(token_payload)

    admin_token = AdminToken(
        token=jwt_token,
        name="测试管理员",
        is_active=True,
        expires_at=None,
    )
    db_session.add(admin_token)
    await db_session.commit()
    await db_session.refresh(admin_token)
    return admin_token


@pytest.fixture
async def exam(db_session) -> Exam:
    """创建测试考试."""
    exam = Exam(
        name="测试考试",
        subject="C语言",
        duration=120,
        start_time=datetime.now(UTC) - timedelta(hours=1),
        end_time=datetime.now(UTC) + timedelta(hours=2),
        status=ExamStatus.IN_PROGRESS,
        pledge_content="# 考前承诺书",
    )
    db_session.add(exam)
    await db_session.commit()
    await db_session.refresh(exam)
    return exam


@pytest.fixture
async def problem(db_session, exam) -> Problem:
    """创建测试题目."""
    problem = Problem(
        exam_id=exam.id,
        title="测试题目",
        content="# 题目内容",
        order_num=1,
    )
    db_session.add(problem)
    await db_session.commit()
    await db_session.refresh(problem)
    return problem


@pytest.fixture
async def student(db_session, exam) -> Student:
    """创建测试考生."""
    student = Student(
        exam_id=exam.id,
        student_id="2024001",
        name="张三",
        login_code=generate_login_code(),
        login_code_used=False,
        submit_status=SubmitStatus.NOT_STARTED,
    )
    db_session.add(student)
    await db_session.commit()
    await db_session.refresh(student)
    return student


class TestStudentLogin:
    """考生登录测试."""

    async def test_login_success(self, client, exam, student):
        """测试登录成功."""
        response = await client.post(
            "/api/auth/student/login",
            json={
                "student_id": student.student_id,
                "name": student.name,
                "login_code": student.login_code,
                "exam_id": exam.id,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "student_token" in data["data"]
        assert data["data"]["exam_info"]["id"] == exam.id

    async def test_login_with_used_code(self, client, exam, student, db_session):
        """测试已使用的登录码."""
        # 先使用一次登录码
        student.login_code_used = True
        await db_session.commit()

        response = await client.post(
            "/api/auth/student/login",
            json={
                "student_id": student.student_id,
                "name": student.name,
                "login_code": student.login_code,
                "exam_id": exam.id,
            },
        )
        assert response.status_code == 400
        data = response.json()
        assert "登录码已使用" in data["message"]

    async def test_login_with_wrong_credentials(self, client, exam, student):
        """测试错误的登录信息."""
        response = await client.post(
            "/api/auth/student/login",
            json={
                "student_id": "999999",
                "name": student.name,
                "login_code": student.login_code,
                "exam_id": exam.id,
            },
        )
        assert response.status_code == 401
        data = response.json()
        assert "登录信息错误" in data["message"]

    async def test_login_with_nonexistent_exam(self, client, student):
        """测试不存在的考试."""
        response = await client.post(
            "/api/auth/student/login",
            json={
                "student_id": student.student_id,
                "name": student.name,
                "login_code": student.login_code,
                "exam_id": 99999,
            },
        )
        assert response.status_code == 404


class TestFullscreenReport:
    """全屏状态上报测试."""

    async def test_fullscreen_success(self, client, exam, student, db_session):
        """测试全屏成功."""
        # 先登录获取 token
        login_response = await client.post(
            "/api/auth/student/login",
            json={
                "student_id": student.student_id,
                "name": student.name,
                "login_code": student.login_code,
                "exam_id": exam.id,
            },
        )
        token = login_response.json()["data"]["student_token"]

        response = await client.post(
            "/api/auth/student/fullscreen",
            json={"success": True},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "websocket_token" in data["data"]
        assert "ws_url" in data["data"]

    async def test_fullscreen_failure(self, client, exam, student, db_session):
        """测试全屏失败."""
        # 先登录获取 token
        login_response = await client.post(
            "/api/auth/student/login",
            json={
                "student_id": student.student_id,
                "name": student.name,
                "login_code": student.login_code,
                "exam_id": exam.id,
            },
        )
        token = login_response.json()["data"]["student_token"]

        response = await client.post(
            "/api/auth/student/fullscreen",
            json={"success": False, "reason": "用户拒绝全屏"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 400
        data = response.json()
        assert "全屏进入失败" in data["message"]

    async def test_fullscreen_with_invalid_token(self, client):
        """测试无效的 Token."""
        response = await client.post(
            "/api/auth/student/fullscreen",
            json={"success": True},
            headers={"Authorization": "Bearer invalid_token"},
        )
        assert response.status_code == 401


class TestStudentList:
    """考生列表测试."""

    async def test_list_students(self, client, exam, student, admin_token):
        """测试获取考生列表."""
        response = await client.get(
            f"/api/admin/exams/{exam.id}/students",
            headers={"Authorization": f"Bearer {admin_token.token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert len(data["data"]) == 1
        assert data["data"][0]["student_id"] == student.student_id

    async def test_list_students_without_auth(self, client, exam):
        """测试无权限访问."""
        response = await client.get(f"/api/admin/exams/{exam.id}/students")
        # FastAPI 会返回 422 因为缺少必需的 Header
        assert response.status_code == 422

    async def test_list_students_with_nonexistent_exam(self, client, admin_token):
        """测试不存在的考试."""
        response = await client.get(
            "/api/admin/exams/99999/students",
            headers={"Authorization": f"Bearer {admin_token.token}"},
        )
        assert response.status_code == 404


class TestImportStudents:
    """批量导入考生测试."""

    async def test_import_students_success(self, client, exam, admin_token, db_session):
        """测试批量导入成功."""
        students_data = [
            {"student_id": "2024002", "name": "李四"},
            {"student_id": "2024003", "name": "王五"},
        ]

        response = await client.post(
            f"/api/admin/exams/{exam.id}/students",
            json=students_data,
            headers={"Authorization": f"Bearer {admin_token.token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert data["data"]["imported_count"] == 2

        # 验证数据库中是否创建
        result = await db_session.execute(select(Student).where(Student.exam_id == exam.id))
        students = result.scalars().all()
        assert len(students) == 2

    async def test_import_students_with_duplicate_ids(self, client, exam, admin_token):
        """测试重复的学号."""
        students_data = [
            {"student_id": "2024002", "name": "李四"},
            {"student_id": "2024002", "name": "王五"},  # 重复学号
        ]

        response = await client.post(
            f"/api/admin/exams/{exam.id}/students",
            json=students_data,
            headers={"Authorization": f"Bearer {admin_token.token}"},
        )
        assert response.status_code == 400
        data = response.json()
        assert "重复的学号" in data["message"]

    async def test_import_students_with_existing_id(self, client, exam, student, admin_token):
        """测试已存在的学号."""
        students_data = [
            {"student_id": student.student_id, "name": "张三"},  # 已存在的学号
        ]

        response = await client.post(
            f"/api/admin/exams/{exam.id}/students",
            json=students_data,
            headers={"Authorization": f"Bearer {admin_token.token}"},
        )
        assert response.status_code == 400
        data = response.json()
        assert "已存在" in data["message"]


class TestStudentDetail:
    """考生详情测试."""

    async def test_get_student_detail(self, client, student, admin_token):
        """测试获取考生详情."""
        response = await client.get(
            f"/api/admin/students/{student.id}",
            headers={"Authorization": f"Bearer {admin_token.token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert data["data"]["student_id"] == student.student_id
        assert data["data"]["name"] == student.name

    async def test_get_nonexistent_student(self, client, admin_token):
        """测试不存在的考生."""
        response = await client.get(
            "/api/admin/students/99999",
            headers={"Authorization": f"Bearer {admin_token.token}"},
        )
        assert response.status_code == 404


class TestForceSubmit:
    """强制收卷测试."""

    async def test_force_submit_success(self, client, student, admin_token, db_session):
        """测试强制收卷成功."""
        response = await client.post(
            f"/api/admin/students/{student.id}/force-submit",
            headers={"Authorization": f"Bearer {admin_token.token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert data["data"]["status"] == "force_submitted"

        # 验证数据库状态
        await db_session.refresh(student)
        assert student.submit_status == SubmitStatus.FORCE_SUBMITTED
        assert student.submit_time is not None

    async def test_force_submit_nonexistent_student(self, client, admin_token):
        """测试不存在的考生."""
        response = await client.post(
            "/api/admin/students/99999/force-submit",
            headers={"Authorization": f"Bearer {admin_token.token}"},
        )
        assert response.status_code == 404


class TestDeleteStudent:
    """删除考生测试."""

    async def test_delete_student_success(self, client, student, admin_token, db_session):
        """测试删除考生成功."""
        student_id = student.id

        response = await client.delete(
            f"/api/admin/students/{student_id}",
            headers={"Authorization": f"Bearer {admin_token.token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert data["data"]["id"] == student_id

        # 验证数据库中已删除
        result = await db_session.execute(select(Student).where(Student.id == student_id))
        assert result.scalar_one_or_none() is None

    async def test_delete_nonexistent_student(self, client, admin_token):
        """测试不存在的考生."""
        response = await client.delete(
            "/api/admin/students/99999",
            headers={"Authorization": f"Bearer {admin_token.token}"},
        )
        assert response.status_code == 404


class TestOperationLog:
    """操作日志测试."""

    async def test_create_log(self, client, exam, student, db_session):
        """测试创建日志."""
        # 先登录获取 token
        login_response = await client.post(
            "/api/auth/student/login",
            json={
                "student_id": student.student_id,
                "name": student.name,
                "login_code": student.login_code,
                "exam_id": exam.id,
            },
        )
        token = login_response.json()["data"]["student_token"]

        response = await client.post(
            "/api/logs",
            json={
                "operation_type": "visibility_change",
                "description": "页面不可见",
                "level": "warning",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert data["data"]["operation_type"] == "visibility_change"

    async def test_list_logs(self, client, exam, student, admin_token, db_session):
        """测试获取日志列表."""
        # 创建一些日志
        log = OperationLog(
            student_id=student.id,
            operation_type="test_operation",
            description="测试操作",
            level=OperationLevel.WARNING,
        )
        db_session.add(log)
        await db_session.commit()

        response = await client.get(
            f"/api/admin/exams/{exam.id}/logs",
            headers={"Authorization": f"Bearer {admin_token.token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert len(data["data"]) >= 1

    async def test_list_logs_with_level_filter(
        self, client, exam, student, admin_token, db_session
    ):
        """测试按级别过滤日志."""
        # 创建不同级别的日志
        warning_log = OperationLog(
            student_id=student.id,
            operation_type="warning_op",
            description="警告操作",
            level=OperationLevel.WARNING,
        )
        normal_log = OperationLog(
            student_id=student.id,
            operation_type="normal_op",
            description="普通操作",
            level=OperationLevel.NORMAL,
        )
        db_session.add(warning_log)
        db_session.add(normal_log)
        await db_session.commit()

        response = await client.get(
            f"/api/admin/exams/{exam.id}/logs?level=warning",
            headers={"Authorization": f"Bearer {admin_token.token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        # 只返回 warning 级别的日志
        for log in data["data"]:
            assert log["level"] == "warning"


class TestDashboard:
    """仪表盘测试."""

    async def test_get_dashboard(self, client, exam, student, admin_token, db_session):
        """测试获取仪表盘数据."""
        # 创建一些测试数据
        student.submit_status = SubmitStatus.SUBMITTED
        student.submit_time = datetime.now(UTC)
        await db_session.commit()

        log = OperationLog(
            student_id=student.id,
            operation_type="warning_op",
            description="警告操作",
            level=OperationLevel.WARNING,
        )
        db_session.add(log)
        await db_session.commit()

        response = await client.get(
            f"/api/admin/dashboard/{exam.id}",
            headers={"Authorization": f"Bearer {admin_token.token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "exam_status" in data["data"]
        assert "countdown" in data["data"]
        assert "submit_count" in data["data"]
        assert "total_count" in data["data"]
        assert "recent_logs" in data["data"]

    async def test_get_dashboard_nonexistent_exam(self, client, admin_token):
        """测试不存在的考试."""
        response = await client.get(
            "/api/admin/dashboard/99999",
            headers={"Authorization": f"Bearer {admin_token.token}"},
        )
        assert response.status_code == 404


class TestAdminAuth:
    """管理员认证测试."""

    async def test_require_admin_valid_token(self, client, admin_token, exam, student):
        """测试有效的管理员 Token."""
        response = await client.get(
            f"/api/admin/exams/{exam.id}/students",
            headers={"Authorization": f"Bearer {admin_token.token}"},
        )
        assert response.status_code == 200

    async def test_require_admin_invalid_token(self, client, exam):
        """测试无效的管理员 Token."""
        response = await client.get(
            f"/api/admin/exams/{exam.id}/students",
            headers={"Authorization": "Bearer invalid_token"},
        )
        assert response.status_code == 401

    async def test_require_admin_no_token(self, client, exam):
        """测试没有 Token."""
        response = await client.get(f"/api/admin/exams/{exam.id}/students")
        # FastAPI 会返回 422 因为缺少必需的 Header
        assert response.status_code == 422

    async def test_require_admin_inactive_token(self, client, admin_token, exam, db_session):
        """测试停用的管理员 Token."""
        # 停用 token
        admin_token.is_active = False
        await db_session.commit()

        response = await client.get(
            f"/api/admin/exams/{exam.id}/students",
            headers={"Authorization": f"Bearer {admin_token.token}"},
        )
        assert response.status_code == 401

    async def test_require_admin_expired_token(self, client, db_session, exam):
        """测试过期的管理员 Token."""

        # 创建已过期的 token
        token_payload = {"type": "admin"}
        jwt_token = create_access_token(token_payload)

        admin_token = AdminToken(
            token=jwt_token,
            name="过期管理员",
            is_active=True,
            expires_at=datetime.now(UTC) - timedelta(days=1),  # 已过期
        )
        db_session.add(admin_token)
        await db_session.commit()

        response = await client.get(
            f"/api/admin/exams/{exam.id}/students",
            headers={"Authorization": f"Bearer {admin_token.token}"},
        )
        assert response.status_code == 401
