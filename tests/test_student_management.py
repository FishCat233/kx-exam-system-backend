"""学生管理和操作相关测试."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models import (
    Admin,
    AdminRole,
    Exam,
    ExamStatus,
    OperationLevel,
    OperationLog,
    Problem,
    Student,
    StudentCode,
    SubmitStatus,
)
from app.utils import generate_login_code
from app.utils.auth import create_access_token, get_password_hash


@pytest.fixture
async def admin_token(db_session) -> Admin:
    """创建管理员账号."""
    admin = Admin(
        username="test_admin",
        password_hash=get_password_hash("test_password"),
        name="测试管理员",
        is_active=True,
        remark="测试用管理员账号",
    )
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)
    return admin


@pytest.fixture
async def super_admin_token(db_session) -> Admin:
    """创建高权限管理员账号."""
    admin = Admin(
        username="test_super_admin",
        password_hash=get_password_hash("test_password"),
        name="测试超级管理员",
        is_active=True,
        role=AdminRole.SUPER_ADMIN,
        remark="测试用高权限管理员账号",
    )
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)
    return admin


def create_admin_jwt_token(admin_id: int) -> str:
    """创建管理员 JWT Token."""
    token_payload = {"type": "admin", "admin_id": admin_id}
    return create_access_token(token_payload)


@pytest.fixture
async def exam(db_session) -> Exam:
    """创建测试考试."""
    exam = Exam(
        name="测试考试",
        subject="C语言",
        duration=120,
        start_time=datetime.now(UTC) - timedelta(hours=1),
        end_time=datetime.now(UTC) + timedelta(hours=2),
        status=ExamStatus.ONGOING,
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

    async def test_list_students(self, client, exam, student, super_admin_token):
        """测试获取考生列表."""
        token = create_admin_jwt_token(super_admin_token.id)
        response = await client.get(
            f"/api/admin/exams/{exam.id}/students",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert len(data["data"]) == 1
        assert data["data"][0]["student_id"] == student.student_id

    async def test_list_students_without_auth(self, client, exam):
        """测试无权限访问."""
        response = await client.get(f"/api/admin/exams/{exam.id}/students")
        # 缺少 Authorization 头返回 401
        assert response.status_code == 401

    async def test_list_students_with_nonexistent_exam(self, client, super_admin_token):
        """测试不存在的考试."""
        token = create_admin_jwt_token(super_admin_token.id)
        response = await client.get(
            "/api/admin/exams/99999/students",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404


class TestImportStudents:
    """批量导入考生测试."""

    async def test_import_students_success(self, client, exam, super_admin_token, db_session):
        """测试批量导入成功."""
        token = create_admin_jwt_token(super_admin_token.id)
        students_data = {
            "students": [
                {"student_id": "2024002", "name": "李四"},
                {"student_id": "2024003", "name": "王五"},
            ]
        }

        response = await client.post(
            f"/api/admin/exams/{exam.id}/students",
            json=students_data,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert data["data"]["imported_count"] == 2

        # 验证数据库中是否创建
        result = await db_session.execute(select(Student).where(Student.exam_id == exam.id))
        students = result.scalars().all()
        assert len(students) == 2

    async def test_import_students_with_duplicate_ids(self, client, exam, super_admin_token):
        """测试重复的学号."""
        token = create_admin_jwt_token(super_admin_token.id)
        students_data = {
            "students": [
                {"student_id": "2024002", "name": "李四"},
                {"student_id": "2024002", "name": "王五"},  # 重复学号
            ]
        }

        response = await client.post(
            f"/api/admin/exams/{exam.id}/students",
            json=students_data,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 400
        data = response.json()
        assert "重复的学号" in data["message"]

    async def test_import_students_with_existing_id(self, client, exam, student, super_admin_token):
        """测试已存在的学号."""
        token = create_admin_jwt_token(super_admin_token.id)
        students_data = {
            "students": [
                {"student_id": student.student_id, "name": "张三"},  # 已存在的学号
            ]
        }

        response = await client.post(
            f"/api/admin/exams/{exam.id}/students",
            json=students_data,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 400
        data = response.json()
        assert "已存在" in data["message"]


class TestStudentDetail:
    """考生详情测试."""

    async def test_get_student_detail(self, client, student, super_admin_token):
        """测试获取考生详情."""
        token = create_admin_jwt_token(super_admin_token.id)
        response = await client.get(
            f"/api/admin/students/{student.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert data["data"]["student_id"] == student.student_id
        assert data["data"]["name"] == student.name
        assert isinstance(data["data"]["logs"], list)
        assert isinstance(data["data"]["codes"], list)

    async def test_get_nonexistent_student(self, client, super_admin_token):
        """测试不存在的考生."""
        token = create_admin_jwt_token(super_admin_token.id)
        response = await client.get(
            "/api/admin/students/99999",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404


class TestForceSubmit:
    """强制收卷测试."""

    async def test_force_submit_success(self, client, student, super_admin_token, db_session):
        """测试强制收卷成功."""
        token = create_admin_jwt_token(super_admin_token.id)
        response = await client.post(
            f"/api/admin/students/{student.id}/force-submit",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert data["data"]["status"] == "force_submitted"

        # 验证数据库状态
        await db_session.refresh(student)
        assert student.submit_status == SubmitStatus.FORCE_SUBMITTED
        assert student.submit_time is not None

    async def test_force_submit_nonexistent_student(self, client, super_admin_token):
        """测试不存在的考生."""
        token = create_admin_jwt_token(super_admin_token.id)
        response = await client.post(
            "/api/admin/students/99999/force-submit",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404


class TestDeleteStudent:
    """删除考生测试."""

    async def test_delete_student_success(self, client, student, super_admin_token, db_session):
        """测试删除考生成功."""
        token = create_admin_jwt_token(super_admin_token.id)
        student_id = student.id

        response = await client.delete(
            f"/api/admin/students/{student_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert data["data"]["id"] == student_id

        # 验证数据库中已删除
        result = await db_session.execute(select(Student).where(Student.id == student_id))
        assert result.scalar_one_or_none() is None

    async def test_delete_nonexistent_student(self, client, super_admin_token):
        """测试不存在的考生."""
        token = create_admin_jwt_token(super_admin_token.id)
        response = await client.delete(
            "/api/admin/students/99999",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404

    async def test_delete_student_removes_related_records(
        self, client, student, problem, super_admin_token, db_session
    ):
        """测试删除考生时会删除关联代码和日志."""
        code = StudentCode(
            student_id=student.id,
            problem_id=problem.id,
            code="int main(void) { return 0; }",
            saved_at=datetime.now(UTC),
        )
        log = OperationLog(
            student_id=student.id,
            operation_type="test_delete",
            description="删除考生前的测试日志",
            level=OperationLevel.NORMAL,
        )
        db_session.add(code)
        db_session.add(log)
        await db_session.commit()

        token = create_admin_jwt_token(super_admin_token.id)
        response = await client.delete(
            f"/api/admin/students/{student.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

        student_result = await db_session.execute(select(Student).where(Student.id == student.id))
        code_result = await db_session.execute(
            select(StudentCode).where(StudentCode.student_id == student.id)
        )
        log_result = await db_session.execute(
            select(OperationLog).where(OperationLog.student_id == student.id)
        )

        assert student_result.scalar_one_or_none() is None
        assert code_result.scalars().all() == []
        assert log_result.scalars().all() == []


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
        token = create_admin_jwt_token(admin_token.id)
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
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert len(data["data"]) >= 1

    async def test_list_logs_with_level_filter(
        self, client, exam, student, admin_token, db_session
    ):
        """测试按级别过滤日志."""
        token = create_admin_jwt_token(admin_token.id)
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
            headers={"Authorization": f"Bearer {token}"},
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
        token = create_admin_jwt_token(admin_token.id)
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
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert data["data"]["exam_status"] == "ongoing"
        assert data["data"]["countdown"] > 0
        assert "submit_count" in data["data"]
        assert "total_count" in data["data"]
        assert "recent_logs" in data["data"]

    async def test_get_dashboard_with_naive_local_time(self, client, admin_token, db_session):
        """测试本地时间存储下仪表盘倒计时仍然正确."""
        exam = Exam(
            name="本地时间考试",
            subject="C语言",
            duration=180,
            start_time=datetime.now() - timedelta(hours=1),
            end_time=datetime.now() + timedelta(hours=2),
            status=ExamStatus.ONGOING,
        )
        db_session.add(exam)
        await db_session.commit()
        await db_session.refresh(exam)

        token = create_admin_jwt_token(admin_token.id)
        response = await client.get(
            f"/api/admin/dashboard/{exam.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["exam_status"] == "ongoing"
        assert 7100 <= data["data"]["countdown"] <= 7300

    async def test_get_dashboard_nonexistent_exam(self, client, admin_token):
        """测试不存在的考试."""
        token = create_admin_jwt_token(admin_token.id)
        response = await client.get(
            "/api/admin/dashboard/99999",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404


class TestAdminAuth:
    """管理员认证测试."""

    async def test_require_admin_valid_token(self, client, super_admin_token, exam, student):
        """测试高权限管理员可以访问考生管理接口."""
        token = create_admin_jwt_token(super_admin_token.id)
        response = await client.get(
            f"/api/admin/exams/{exam.id}/students",
            headers={"Authorization": f"Bearer {token}"},
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
        # 缺少 Authorization 头返回 401
        assert response.status_code == 401

    async def test_require_admin_deactivated_account(
        self, client, db_session, super_admin_token, exam
    ):
        """测试已停用的高权限管理员账号."""
        from app.utils.auth import create_access_token as auth_create_access_token

        # 停用账号
        super_admin_token.is_active = False
        await db_session.commit()

        # 生成 JWT Token
        token_payload = {"type": "admin", "admin_id": super_admin_token.id}
        jwt_token = auth_create_access_token(token_payload)

        response = await client.get(
            f"/api/admin/exams/{exam.id}/students",
            headers={"Authorization": f"Bearer {jwt_token}"},
        )
        assert response.status_code == 403

    async def test_regular_admin_cannot_manage_students(self, client, admin_token, exam):
        """测试普通管理员不能访问考生管理接口."""
        token = create_admin_jwt_token(admin_token.id)
        response = await client.get(
            f"/api/admin/exams/{exam.id}/students",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403

    async def test_require_admin_deleted_account(self, client, db_session, exam):
        """测试已删除的管理员账号."""
        # 创建并删除管理员
        from app.models import Admin
        from app.utils.auth import create_access_token as auth_create_access_token
        from app.utils.auth import get_password_hash

        admin = Admin(
            username="temp_admin",
            password_hash=get_password_hash("password"),
            name="Temp Admin",
            is_active=True,
        )
        db_session.add(admin)
        await db_session.commit()
        await db_session.refresh(admin)
        admin_id = admin.id

        # 删除管理员
        await db_session.delete(admin)
        await db_session.commit()

        # 使用已删除管理员的 ID 生成 Token
        token_payload = {"type": "admin", "admin_id": admin_id}
        jwt_token = auth_create_access_token(token_payload)

        response = await client.get(
            f"/api/admin/exams/{exam.id}/students",
            headers={"Authorization": f"Bearer {jwt_token}"},
        )
        assert response.status_code == 401
