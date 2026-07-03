"""代码相关路由."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Exam, ExamStatus, Student, StudentCode, SubmitStatus
from app.schemas import (
    CodeResponse,
    CodeSaveRequest,
    CodeSaveResponse,
    CodeSubmitResponse,
    ResponseModel,
)
from app.utils import require_student

router = APIRouter(prefix="/api/code", tags=["代码"])


@router.get(
    "/{problem_id}",
    response_model=ResponseModel[CodeResponse],
    summary="获取题目代码",
    description="获取当前考生指定题目的代码记录。如果没有记录，返回空字符串。",
)
async def get_code(
    problem_id: int,
    student: Student = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> ResponseModel[CodeResponse]:
    """获取题目代码.

    Args:
        problem_id: 题目ID
        student: 当前考生对象
        db: 数据库会话

    Returns:
        包含代码内容和保存时间的响应
    """
    result = await db.execute(
        select(StudentCode).where(
            StudentCode.student_id == student.id,
            StudentCode.problem_id == problem_id,
        )
    )
    code_record = result.scalar_one_or_none()

    if code_record is None:
        return ResponseModel(
            data=CodeResponse(code="", saved_at=None),
            message="暂无代码记录",
        )

    return ResponseModel(
        data=CodeResponse(
            code=code_record.code,
            saved_at=code_record.saved_at,
        ),
        message="获取代码成功",
    )


@router.post(
    "/{problem_id}",
    response_model=ResponseModel[CodeSaveResponse],
    summary="保存代码",
    description="保存考生代码。如果记录不存在则创建，存在则更新。首次保存时会将考生状态更新为进行中。",
)
async def save_code(
    problem_id: int,
    request: CodeSaveRequest,
    student: Student = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> ResponseModel[CodeSaveResponse]:
    """保存代码.

    Args:
        problem_id: 题目ID
        request: 保存代码请求
        student: 当前考生对象
        db: 数据库会话

    Returns:
        包含保存时间的响应

    Raises:
        HTTPException: 400 - 考试已结束
    """
    # 检查考试状态 - 直接查询 Exam 表避免懒加载问题
    exam_result = await db.execute(select(Exam).where(Exam.id == student.exam_id))
    exam = exam_result.scalar_one_or_none()
    if exam is None or exam.status == ExamStatus.ENDED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="考试已结束，无法保存代码",
        )

    # 查询是否已存在代码记录
    result = await db.execute(
        select(StudentCode).where(
            StudentCode.student_id == student.id,
            StudentCode.problem_id == problem_id,
        )
    )
    code_record = result.scalar_one_or_none()

    now = datetime.now(UTC)

    if code_record is None:
        # 创建新记录
        code_record = StudentCode(
            student_id=student.id,
            problem_id=problem_id,
            code=request.code,
            saved_at=now,
        )
        db.add(code_record)
    else:
        # 更新现有记录
        code_record.code = request.code
        code_record.saved_at = now

    # 首次保存时更新考生状态为进行中
    if student.submit_status == SubmitStatus.NOT_STARTED:
        student.submit_status = SubmitStatus.IN_PROGRESS

    await db.commit()
    await db.refresh(code_record)

    return ResponseModel(
        data=CodeSaveResponse(saved_at=code_record.saved_at),
        message="保存代码成功",
    )


@router.post(
    "/submit",
    response_model=ResponseModel[CodeSubmitResponse],
    summary="提交代码（交卷）",
    description="提交代码并完成交卷。检查考生状态和考试状态后，更新交卷状态和时间。",
)
async def submit_exam(
    student: Student = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> ResponseModel[CodeSubmitResponse]:
    """提交代码（交卷）.

    Args:
        student: 当前考生对象
        db: 数据库会话

    Returns:
        包含交卷时间和状态的响应

    Raises:
        HTTPException: 400 - 已经交卷或考试已结束
    """
    # 检查考试状态 - 直接查询 Exam 表避免懒加载问题
    exam_result = await db.execute(select(Exam).where(Exam.id == student.exam_id))
    exam = exam_result.scalar_one_or_none()
    if exam is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="考试不存在",
        )
    if exam.status != ExamStatus.ONGOING:
        msg: dict[ExamStatus, str] = {
            ExamStatus.NOT_STARTED: "考试尚未开始",
            ExamStatus.ENDED: "考试已结束，无法提交",
        }
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg.get(exam.status, "考试状态异常"),
        )

    # 原子更新交卷状态 — 使用 UPDATE ... WHERE 避免 TOCTOU 竞态条件
    # 只有 submit_status 仍为 NOT_STARTED 或 IN_PROGRESS 时才会更新成功
    now = datetime.now(UTC)
    result = await db.execute(
        update(Student)
        .where(
            Student.id == student.id,
            Student.submit_status.not_in(
                [SubmitStatus.SUBMITTED, SubmitStatus.FORCE_SUBMITTED]
            ),
        )
        .values(submit_status=SubmitStatus.SUBMITTED, submit_time=now)
    )
    await db.commit()

    if result.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="您已经交卷，无法重复提交",
        )

    # 刷新 ORM 对象以同步数据库最新值
    await db.refresh(student)

    return ResponseModel(
        data=CodeSubmitResponse(
            submit_time=student.submit_time,
            status=student.submit_status,
        ),
        message="交卷成功",
    )
