"""考试数据导出工具函数."""

import csv
import io
import json
import logging
import re
import zipfile
from datetime import UTC, datetime

from app.models import Exam, OperationLog, Problem, Student, StudentCode

logger = logging.getLogger(__name__)

UTF8_BOM = "\ufeff"


def sanitize_filename(filename: str) -> str:
    """清理文件名中的特殊字符.

    将文件名中的非法字符替换为下划线，确保文件名在各类文件系统中合法。

    Args:
        filename: 原始文件名

    Returns:
        清理后的安全文件名
    """
    # Windows 和 Unix 系统中的非法字符
    illegal_chars = r'[<>:"/\\|?*\x00-\x1f]'
    # 替换非法字符为下划线
    sanitized = re.sub(illegal_chars, "_", filename)
    # 去除首尾空格和点
    sanitized = sanitized.strip(" .")
    # 限制长度，避免路径过长
    if len(sanitized) > 200:
        sanitized = sanitized[:200]
    # 如果文件名为空，使用默认名称
    if not sanitized:
        sanitized = "unnamed"
    return sanitized


def format_datetime(value: datetime | None) -> str:
    """将 datetime 转换为 ISO 字符串."""

    if value is None:
        return ""
    return value.isoformat()


def build_csv(rows: list[list[str]]) -> str:
    """构建带 UTF-8 BOM 的 CSV 文本."""

    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerows(rows)
    return UTF8_BOM + buffer.getvalue()


def generate_exam_export(
    exam: Exam,
    students: list[Student],
    student_codes_map: dict[int, list[StudentCode]],
    problems_map: dict[int, Problem],
    operation_logs_map: dict[int, list[OperationLog]],
) -> tuple[bytes, str]:
    """生成考试数据导出 ZIP 文件.

    将考试的所有考生代码打包成 ZIP 文件，目录结构如下：
    {exam_name}/
      {student_id}_{student_name}/
        problem_{order_num}_{title}.c
        ...

    Args:
        exam: 考试对象
        students: 考生列表
        student_codes_map: 考生代码映射，key 为 student_id，value 为代码列表
        problems_map: 题目映射，key 为 problem_id，value 为题目对象
        operation_logs_map: 考生日志映射，key 为 student_id，value 为日志列表

    Returns:
        tuple: (ZIP 文件字节内容, 建议的文件名)

    Raises:
        ValueError: 当输入数据无效时
    """
    if exam is None:
        raise ValueError("考试对象不能为空")

    # 清理考试名称用于目录名
    exam_dir_name = sanitize_filename(exam.name)

    # 生成 ZIP 文件名
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    zip_filename = f"{exam_dir_name}_{timestamp}.zip"

    # 创建内存中的 ZIP 文件
    zip_buffer = io.BytesIO()
    ordered_problems = sorted(
        problems_map.values(), key=lambda problem: (problem.order_num, problem.id)
    )

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        # 记录导出的文件数量
        total_files = 0
        total_students = 0
        total_logs = sum(len(logs) for logs in operation_logs_map.values())
        students_csv_rows = [
            [
                "student_db_id",
                "student_id",
                "name",
                "login_code",
                "login_code_used",
                "login_time",
                "submit_time",
                "submit_status",
                "is_fullscreen",
                "code_file_count",
                "latest_saved_at",
            ]
        ]
        problems_csv_rows = [
            [
                "problem_id",
                "order_num",
                "title",
                "content_preview",
            ]
        ]
        grading_template_rows = [
            [
                "student_id",
                "name",
                "submit_status",
                "login_time",
                "submit_time",
                *[
                    f"problem_{problem.order_num:02d}_{problem.title}"
                    for problem in ordered_problems
                ],
                "total_score",
                "comment",
            ]
        ]
        operation_logs_csv_rows = [
            [
                "log_id",
                "student_db_id",
                "student_id",
                "student_name",
                "operation_type",
                "description",
                "level",
                "ip_address",
                "user_agent",
                "created_at",
            ]
        ]
        operation_logs_json: list[dict[str, str | int | None]] = []

        for problem in ordered_problems:
            problems_csv_rows.append(
                [
                    str(problem.id),
                    str(problem.order_num),
                    problem.title,
                    (problem.content[:120] + "...")
                    if len(problem.content) > 120
                    else problem.content,
                ]
            )

        for student in students:
            # 清理考生信息用于目录名
            safe_student_id = sanitize_filename(student.student_id)
            safe_student_name = sanitize_filename(student.name)
            student_dir_name = f"{safe_student_id}_{safe_student_name}"
            student_path = f"{exam_dir_name}/{student_dir_name}"

            # 获取该考生的代码列表
            codes = sorted(
                student_codes_map.get(student.id, []),
                key=lambda code: (
                    problems_map.get(code.problem_id).order_num
                    if problems_map.get(code.problem_id)
                    else code.problem_id
                ),
            )
            logs = sorted(
                operation_logs_map.get(student.id, []),
                key=lambda log: log.created_at,
            )
            latest_saved_at = max((code.saved_at for code in codes if code.saved_at), default=None)

            students_csv_rows.append(
                [
                    str(student.id),
                    student.student_id,
                    student.name,
                    student.login_code,
                    "true" if student.login_code_used else "false",
                    format_datetime(student.login_time),
                    format_datetime(student.submit_time),
                    student.submit_status.value,
                    "true" if student.is_fullscreen else "false",
                    str(len(codes)),
                    format_datetime(latest_saved_at),
                ]
            )
            grading_template_rows.append(
                [
                    student.student_id,
                    student.name,
                    student.submit_status.value,
                    format_datetime(student.login_time),
                    format_datetime(student.submit_time),
                    *([""] * len(ordered_problems)),
                    "",
                    "",
                ]
            )

            for log in logs:
                operation_logs_csv_rows.append(
                    [
                        str(log.id),
                        str(student.id),
                        student.student_id,
                        student.name,
                        log.operation_type,
                        log.description,
                        log.level.value,
                        log.ip_address or "",
                        log.user_agent or "",
                        format_datetime(log.created_at),
                    ]
                )
                operation_logs_json.append(
                    {
                        "log_id": log.id,
                        "student_db_id": student.id,
                        "student_id": student.student_id,
                        "student_name": student.name,
                        "operation_type": log.operation_type,
                        "description": log.description,
                        "level": log.level.value,
                        "ip_address": log.ip_address,
                        "user_agent": log.user_agent,
                        "created_at": format_datetime(log.created_at),
                    }
                )

            if not codes:
                # 考生没有代码，创建一个空目录标记文件
                readme_content = (
                    f"# {student.name} ({student.student_id})\n\n该考生没有提交任何代码。\n"
                )
                readme_path = f"{student_path}/README.md"
                zip_file.writestr(readme_path, readme_content)
                total_files += 1
            else:
                for code in codes:
                    problem = problems_map.get(code.problem_id)
                    if problem:
                        safe_title = sanitize_filename(problem.title)
                        file_name = f"problem_{problem.order_num:02d}_{safe_title}.c"
                    else:
                        file_name = f"problem_{code.problem_id:02d}_unknown.c"

                    file_path = f"{student_path}/{file_name}"

                    # 写入代码文件
                    code_content = code.code if code.code else ""
                    zip_file.writestr(file_path, code_content)
                    total_files += 1

            total_students += 1

        # 如果没有考生，创建一个说明文件
        if not students:
            readme_path = f"{exam_dir_name}/README.md"
            readme_content = f"# {exam.name}\n\n该考试没有考生数据。\n"
            zip_file.writestr(readme_path, readme_content)
            total_files += 1

        zip_file.writestr(f"{exam_dir_name}/students.csv", build_csv(students_csv_rows))
        zip_file.writestr(f"{exam_dir_name}/problems.csv", build_csv(problems_csv_rows))
        zip_file.writestr(f"{exam_dir_name}/grading_template.csv", build_csv(grading_template_rows))
        zip_file.writestr(f"{exam_dir_name}/operation_logs.csv", build_csv(operation_logs_csv_rows))
        zip_file.writestr(
            f"{exam_dir_name}/operation_logs.json",
            json.dumps(operation_logs_json, ensure_ascii=False, indent=2),
        )
        zip_file.writestr(
            f"{exam_dir_name}/exam_summary.json",
            json.dumps(
                {
                    "exam": {
                        "id": exam.id,
                        "name": exam.name,
                        "subject": exam.subject,
                        "duration": exam.duration,
                        "start_time": format_datetime(exam.start_time),
                        "end_time": format_datetime(exam.end_time),
                    },
                    "summary": {
                        "student_count": total_students,
                        "problem_count": len(ordered_problems),
                        "code_file_count": sum(len(codes) for codes in student_codes_map.values()),
                        "operation_log_count": total_logs,
                        "exported_at": datetime.now(UTC).isoformat(),
                    },
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
        total_files += 6

        # 添加导出信息文件
        export_info_path = f"{exam_dir_name}/export_info.txt"
        export_info_content = f"""考试数据导出信息
================

考试名称: {exam.name}
考试科目: {exam.subject}
导出时间: {datetime.now(UTC).isoformat()}
考生数量: {total_students}
题目数量: {len(ordered_problems)}
操作日志数量: {total_logs}
导出文件数量: {total_files}

目录结构说明:
- 每个考生一个文件夹，命名格式: {{学号}}_{{姓名}}
- 每个代码文件对应一道题目，命名格式: problem_{{题号}}_{{标题}}.c
- students.csv: 考生基础信息
- problems.csv: 题目清单
- grading_template.csv: 阅卷模板
- operation_logs.csv / operation_logs.json: 操作日志
- exam_summary.json: 导出摘要
"""
        zip_file.writestr(export_info_path, export_info_content)

    # 记录导出日志
    logger.info(
        f"考试导出完成: exam_id={exam.id}, name={exam.name}, "
        f"students={total_students}, files={total_files}"
    )

    # 获取 ZIP 文件字节内容
    zip_buffer.seek(0)
    zip_bytes = zip_buffer.getvalue()

    return zip_bytes, zip_filename
