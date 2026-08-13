"""代码相关路由."""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import (
    Exam,
    ExamStatus,
    OperationLevel,
    OperationLog,
    Problem,
    Student,
    StudentCode,
    SubmitStatus,
)
from app.schemas import (
    CodeResponse,
    CodeSaveRequest,
    CodeSaveResponse,
    CodeSubmitResponse,
    ResponseModel,
)
from app.services.websocket import ws_manager
from app.utils import require_student

router = APIRouter(prefix="/api/code", tags=["代码"])

# 保存代码被拒日志的去重窗口（秒）
_BLOCK_LOG_DEDUP_WINDOW = 60


async def _log_block_no_ws(
    student: Student,
    db: AsyncSession,
    operation_type: str,
    description: str,
) -> None:
    """记录无 WS 连接的拦截日志，窗口内去重."""
    dedup_result = await db.execute(
        select(OperationLog)
        .where(
            OperationLog.student_id == student.id,
            OperationLog.operation_type == operation_type,
        )
        .order_by(OperationLog.created_at.desc())
        .limit(1)
    )
    recent = dedup_result.scalar_one_or_none()
    duplicated = (
        recent is not None
        and recent.created_at is not None
        and datetime.now(UTC) - recent.created_at < timedelta(seconds=_BLOCK_LOG_DEDUP_WINDOW)
    )
    if duplicated:
        return

    log = OperationLog(
        student_id=student.id,
        operation_type=operation_type,
        description=description,
        level=OperationLevel.CRITICAL,
    )
    db.add(log)
    await db.commit()


def _check_student_active(student: Student) -> None:
    """检查考生是否已交卷或强制收卷."""
    if student.submit_status in (SubmitStatus.SUBMITTED, SubmitStatus.FORCE_SUBMITTED):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您已交卷，无法操作",
        )


@router.post(
    "/submit",
    response_model=ResponseModel[CodeSubmitResponse],
    summary="提交代码（交卷）",
    description="提交代码并完成交卷。",
)
async def submit_exam(
    student: Student = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> ResponseModel[CodeSubmitResponse]:
    """提交代码（交卷）."""
    _check_student_active(student)

    # 检查考试状态
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

    # 原子更新 — 仅 NOT_STARTED 或 IN_PROGRESS 时可以交卷
    now = datetime.now(UTC)
    result = await db.execute(
        update(Student)
        .where(
            Student.id == student.id,
            Student.submit_status.not_in([SubmitStatus.SUBMITTED, SubmitStatus.FORCE_SUBMITTED]),
        )
        .values(submit_status=SubmitStatus.SUBMITTED, submit_time=now)
    )
    await db.commit()

    if result.rowcount == 0:  # type: ignore[union-attr]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="您已经交卷，无法重复提交",
        )

    await db.refresh(student)

    # 后端自主判断：交卷时 WS 不在线，说明监控通道缺失，放行交卷但记录 critical 日志
    if not ws_manager.is_connected(student.id):
        log = OperationLog(
            student_id=student.id,
            operation_type="websocket_missing_at_submit",
            description="交卷时 WebSocket 未连接，监控通道缺失",
            level=OperationLevel.CRITICAL,
        )
        db.add(log)
        await db.commit()

    return ResponseModel(
        data=CodeSubmitResponse(
            submit_time=now,
            status=student.submit_status,
        ),
        message="交卷成功",
    )


@router.get(
    "/{problem_id}",
    response_model=ResponseModel[CodeResponse],
    summary="获取题目代码",
    description="获取当前考生指定题目的代码记录。",
)
async def get_code(
    problem_id: int,
    student: Student = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> ResponseModel[CodeResponse]:
    """获取题目代码."""
    _check_student_active(student)

    problem_result = await db.execute(
        select(Problem).where(
            Problem.id == problem_id,
            Problem.exam_id == student.exam_id,
        )
    )

    if problem_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="题目不存在",
        )

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
    description="保存考生代码。使用 upsert 避免并发重复。",
)
async def save_code(
    problem_id: int,
    request: CodeSaveRequest,
    student: Student = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> ResponseModel[CodeSaveResponse]:
    """保存代码."""
    _check_student_active(student)

    # 检查考试状态
    exam_result = await db.execute(select(Exam).where(Exam.id == student.exam_id).with_for_update())
    exam = exam_result.scalar_one_or_none()
    if exam is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="考试不存在",
        )
    if exam.status != ExamStatus.ONGOING:
        msg = {
            ExamStatus.NOT_STARTED: "考试尚未开始，无法保存代码",
            ExamStatus.ENDED: "考试已结束，无法保存代码",
        }
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg.get(exam.status, "考试状态异常"),
        )

    # 只有建立过 WebSocket 连接的考生才能开始答题（断连后不阻断）
    if not ws_manager.has_ever_connected(student.id):
        await _log_block_no_ws(
            student,
            db,
            "websocket_never_connected",
            "保存代码被拒绝：从未建立 WebSocket 连接",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="监控连接未建立，无法开始答题",
        )

    # 检查题目
    problem_result = await db.execute(
        select(Problem).where(
            Problem.id == problem_id,
            Problem.exam_id == student.exam_id,
        )
    )
    if problem_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="题目不存在",
        )

    now = datetime.now(UTC)

    # Upsert: INSERT ON CONFLICT DO UPDATE
    stmt = insert(StudentCode).values(
        student_id=student.id,
        problem_id=problem_id,
        code=request.code,
        saved_at=now,
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_student_code_per_problem",
        set_={"code": request.code, "saved_at": now},
    )
    await db.execute(stmt)

    # 首次保存时更新考生状态
    await db.execute(
        update(Student)
        .where(
            Student.id == student.id,
            Student.submit_status == SubmitStatus.NOT_STARTED,
        )
        .values(submit_status=SubmitStatus.IN_PROGRESS)
    )

    await db.commit()

    return ResponseModel(
        data=CodeSaveResponse(saved_at=now),
        message="保存代码成功",
    )
