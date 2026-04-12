"""考试数据导出功能测试."""

import io
import zipfile
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AdminToken, Exam, ExamStatus, Problem, Student, StudentCode, SubmitStatus
from app.utils.auth import create_access_token


async def create_admin_token_for_test(db_session: AsyncSession) -> str:
    """创建测试用的管理员 Token.

    Args:
        db_session: 数据库会话

    Returns:
        JWT Token 字符串
    """
    token_payload = {"type": "admin", "admin_id": None}
    jwt_token = create_access_token(token_payload, expires_delta=timedelta(hours=1))

    admin_token = AdminToken(
        token=jwt_token,
        name="Test Admin Token",
        is_active=True,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    db_session.add(admin_token)
    await db_session.commit()
    await db_session.refresh(admin_token)

    return jwt_token


async def create_test_exam(db_session: AsyncSession) -> Exam:
    """创建测试考试.

    Args:
        db_session: 数据库会话

    Returns:
        创建的考试对象
    """
    exam = Exam(
        name="C语言期中考试",
        subject="C语言",
        duration=120,
        start_time=datetime.now(UTC),
        end_time=datetime.now(UTC) + timedelta(hours=2),
        status=ExamStatus.IN_PROGRESS,
        pledge_content="# 考前承诺书",
    )
    db_session.add(exam)
    await db_session.commit()
    await db_session.refresh(exam)
    return exam


async def create_test_problems(db_session: AsyncSession, exam_id: int) -> list[Problem]:
    """创建测试题目.

    Args:
        db_session: 数据库会话
        exam_id: 考试 ID

    Returns:
        创建的题目列表
    """
    problems = [
        Problem(
            exam_id=exam_id,
            title="Hello World",
            content="编写程序输出 Hello World",
            order_num=1,
        ),
        Problem(
            exam_id=exam_id,
            title="两数之和",
            content="计算两个数的和",
            order_num=2,
        ),
    ]
    for problem in problems:
        db_session.add(problem)
    await db_session.commit()

    # 刷新以获取 ID
    for problem in problems:
        await db_session.refresh(problem)

    return problems


async def create_test_students(db_session: AsyncSession, exam_id: int) -> list[Student]:
    """创建测试考生.

    Args:
        db_session: 数据库会话
        exam_id: 考试 ID

    Returns:
        创建的考生列表
    """
    students = [
        Student(
            exam_id=exam_id,
            student_id="2021001",
            name="张三",
            login_code="ABC123",
            login_code_used=True,
            login_time=datetime.now(UTC),
            submit_status=SubmitStatus.IN_PROGRESS,
        ),
        Student(
            exam_id=exam_id,
            student_id="2021002",
            name="李四",
            login_code="DEF456",
            login_code_used=True,
            login_time=datetime.now(UTC),
            submit_status=SubmitStatus.IN_PROGRESS,
        ),
    ]
    for student in students:
        db_session.add(student)
    await db_session.commit()

    # 刷新以获取 ID
    for student in students:
        await db_session.refresh(student)

    return students


async def create_test_student_codes(
    db_session: AsyncSession,
    students: list[Student],
    problems: list[Problem],
) -> None:
    """创建测试考生代码.

    Args:
        db_session: 数据库会话
        students: 考生列表
        problems: 题目列表
    """
    codes = [
        # 张三的代码
        StudentCode(
            student_id=students[0].id,
            problem_id=problems[0].id,
            code='#include <stdio.h>\n\nint main() {\n    printf("Hello World");\n    return 0;\n}',
            saved_at=datetime.now(UTC),
        ),
        StudentCode(
            student_id=students[0].id,
            problem_id=problems[1].id,
            code='#include <stdio.h>\n\nint main() {\n    int a, b;\n    scanf("%d %d", &a, &b);\n    printf("%d", a + b);\n    return 0;\n}',
            saved_at=datetime.now(UTC),
        ),
        # 李四的代码（只有一题）
        StudentCode(
            student_id=students[1].id,
            problem_id=problems[0].id,
            code='#include <stdio.h>\n\nint main() {\n    printf("Hello");\n    return 0;\n}',
            saved_at=datetime.now(UTC),
        ),
    ]
    for code in codes:
        db_session.add(code)
    await db_session.commit()


# ==================== 导出功能测试 ====================


@pytest.mark.asyncio
async def test_export_exam_success(client: AsyncClient, db_session: AsyncSession):
    """测试成功导出考试数据."""
    # 创建测试数据
    admin_token = await create_admin_token_for_test(db_session)
    exam = await create_test_exam(db_session)
    problems = await create_test_problems(db_session, exam.id)
    students = await create_test_students(db_session, exam.id)
    await create_test_student_codes(db_session, students, problems)

    # 调用导出接口
    response = await client.get(
        f"/api/admin/exams/{exam.id}/export",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert "attachment" in response.headers["content-disposition"]
    assert ".zip" in response.headers["content-disposition"]

    # 验证 ZIP 文件内容
    zip_bytes = response.content
    zip_buffer = io.BytesIO(zip_bytes)

    with zipfile.ZipFile(zip_buffer, "r") as zip_file:
        # 检查文件列表
        file_list = zip_file.namelist()
        print(f"ZIP file list: {file_list}")  # 调试输出

        # 应该有导出信息文件
        assert any("export_info.txt" in f for f in file_list)

        # 检查考生目录结构 (使用 / 或 \ 作为路径分隔符)
        assert any("2021001_张三" in f for f in file_list)
        assert any("2021002_李四" in f for f in file_list)

        # 检查代码文件 (只检查文件名部分) - 注意文件名中可能包含空格
        assert any("problem_01_Hello" in f and f.endswith(".c") for f in file_list)
        assert any("problem_02_两数之和" in f and f.endswith(".c") for f in file_list)

        # 验证代码内容
        zhangsan_files = [f for f in file_list if "2021001_张三" in f and f.endswith(".c")]
        assert len(zhangsan_files) == 2, (
            f"Expected 2 files for zhangsan, got: {zhangsan_files}"
        )  # 张三有两道题的代码

        lisi_files = [f for f in file_list if "2021002_李四" in f and f.endswith(".c")]
        assert len(lisi_files) == 1, (
            f"Expected 1 file for lisi, got: {lisi_files}"
        )  # 李四只有一道题的代码

        # 读取并验证代码内容
        for file_path in zhangsan_files:
            content = zip_file.read(file_path).decode("utf-8")
            assert "#include <stdio.h>" in content


@pytest.mark.asyncio
async def test_export_exam_not_found(client: AsyncClient, db_session: AsyncSession):
    """测试导出不存在的考试."""
    admin_token = await create_admin_token_for_test(db_session)

    response = await client.get(
        "/api/admin/exams/9999/export",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_export_exam_no_auth(client: AsyncClient, db_session: AsyncSession):
    """测试导出时无管理员权限."""
    exam = await create_test_exam(db_session)

    # 不携带 Token - 返回 401 (未授权)
    response = await client.get(f"/api/admin/exams/{exam.id}/export")
    assert response.status_code == 401

    # 携带无效 Token - 业务层返回 401
    response = await client.get(
        f"/api/admin/exams/{exam.id}/export",
        headers={"Authorization": "Bearer invalid_token"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_export_exam_inactive_token(client: AsyncClient, db_session: AsyncSession):
    """测试使用已停用的 Token 导出."""
    exam = await create_test_exam(db_session)

    # 创建 Token
    token_payload = {"type": "admin", "admin_id": None}
    jwt_token = create_access_token(token_payload, expires_delta=timedelta(hours=1))

    admin_token = AdminToken(
        token=jwt_token,
        name="Inactive Token",
        is_active=False,  # 已停用
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    db_session.add(admin_token)
    await db_session.commit()

    response = await client.get(
        f"/api/admin/exams/{exam.id}/export",
        headers={"Authorization": f"Bearer {jwt_token}"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_export_exam_no_students(client: AsyncClient, db_session: AsyncSession):
    """测试导出无考生的考试."""
    admin_token = await create_admin_token_for_test(db_session)
    exam = await create_test_exam(db_session)

    response = await client.get(
        f"/api/admin/exams/{exam.id}/export",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200

    # 验证 ZIP 文件内容
    zip_bytes = response.content
    zip_buffer = io.BytesIO(zip_bytes)

    with zipfile.ZipFile(zip_buffer, "r") as zip_file:
        file_list = zip_file.namelist()

        # 应该有导出信息文件和 README
        assert any("export_info.txt" in f for f in file_list)
        assert any("README.md" in f for f in file_list)


@pytest.mark.asyncio
async def test_export_exam_student_no_codes(client: AsyncClient, db_session: AsyncSession):
    """测试导出考生无代码的情况."""
    admin_token = await create_admin_token_for_test(db_session)
    exam = await create_test_exam(db_session)
    await create_test_problems(db_session, exam.id)
    await create_test_students(db_session, exam.id)
    # 不创建代码记录

    response = await client.get(
        f"/api/admin/exams/{exam.id}/export",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200

    # 验证 ZIP 文件内容
    zip_bytes = response.content
    zip_buffer = io.BytesIO(zip_bytes)

    with zipfile.ZipFile(zip_buffer, "r") as zip_file:
        file_list = zip_file.namelist()

        # 考生目录应该存在，但有 README 说明没有代码
        student_dir = "C语言期中考试/2021001_张三/README.md"
        assert any(student_dir in f for f in file_list)


@pytest.mark.asyncio
async def test_export_exam_special_chars_in_name(client: AsyncClient, db_session: AsyncSession):
    """测试考试名称包含特殊字符的导出."""
    admin_token = await create_admin_token_for_test(db_session)

    # 创建包含特殊字符的考试
    exam = Exam(
        name='C语言考试<>:"/\\|?*测试',
        subject="C语言",
        duration=120,
        start_time=datetime.now(UTC),
        end_time=datetime.now(UTC) + timedelta(hours=2),
        status=ExamStatus.IN_PROGRESS,
    )
    db_session.add(exam)
    await db_session.commit()
    await db_session.refresh(exam)

    # 创建包含特殊字符的考生
    student = Student(
        exam_id=exam.id,
        student_id='2021<>:"/\\|?*001',
        name='张<>:"/\\|?*三',
        login_code="ABC123",
        login_code_used=True,
        submit_status=SubmitStatus.IN_PROGRESS,
    )
    db_session.add(student)
    await db_session.commit()

    response = await client.get(
        f"/api/admin/exams/{exam.id}/export",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200

    # 验证 ZIP 文件可以正常打开
    zip_bytes = response.content
    zip_buffer = io.BytesIO(zip_bytes)

    with zipfile.ZipFile(zip_buffer, "r") as zip_file:
        file_list = zip_file.namelist()
        # 文件列表不应该包含原始特殊字符
        for file_path in file_list:
            assert "<" not in file_path or file_path.endswith(".md")
            assert ">" not in file_path or file_path.endswith(".md")


@pytest.mark.asyncio
async def test_export_zip_content_correctness(client: AsyncClient, db_session: AsyncSession):
    """测试 ZIP 文件内容的正确性."""
    admin_token = await create_admin_token_for_test(db_session)
    exam = await create_test_exam(db_session)
    problems = await create_test_problems(db_session, exam.id)
    students = await create_test_students(db_session, exam.id)
    await create_test_student_codes(db_session, students, problems)

    response = await client.get(
        f"/api/admin/exams/{exam.id}/export",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200

    zip_bytes = response.content
    zip_buffer = io.BytesIO(zip_bytes)

    with zipfile.ZipFile(zip_buffer, "r") as zip_file:
        # 获取文件列表
        file_list = zip_file.namelist()

        # 验证 export_info.txt 内容
        info_path = [f for f in file_list if "export_info.txt" in f][0]
        info_content = zip_file.read(info_path).decode("utf-8")
        assert "考试名称: C语言期中考试" in info_content
        assert "考试科目: C语言" in info_content
        assert "考生数量: 2" in info_content

        # 验证张三的第一题代码 - 动态查找文件路径
        zhangsan_code1_path = [f for f in file_list if "2021001_张三" in f and "problem_01" in f][0]
        zhangsan_code1 = zip_file.read(zhangsan_code1_path).decode("utf-8")
        assert 'printf("Hello World")' in zhangsan_code1

        # 验证张三的第二题代码
        zhangsan_code2_path = [f for f in file_list if "2021001_张三" in f and "problem_02" in f][0]
        zhangsan_code2 = zip_file.read(zhangsan_code2_path).decode("utf-8")
        assert "a + b" in zhangsan_code2

        # 验证李四的代码
        lisi_code_path = [f for f in file_list if "2021002_李四" in f and "problem_01" in f][0]
        lisi_code = zip_file.read(lisi_code_path).decode("utf-8")
        assert 'printf("Hello")' in lisi_code
