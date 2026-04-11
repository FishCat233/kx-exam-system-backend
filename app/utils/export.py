"""考试数据导出工具函数."""

import io
import logging
import re
import zipfile
from datetime import UTC, datetime

from app.models import Exam, Problem, Student, StudentCode

logger = logging.getLogger(__name__)


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


def generate_exam_export(
    exam: Exam,
    students: list[Student],
    student_codes_map: dict[int, list[StudentCode]],
    problems_map: dict[int, Problem],
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

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        # 记录导出的文件数量
        total_files = 0
        total_students = 0

        for student in students:
            # 清理考生信息用于目录名
            safe_student_id = sanitize_filename(student.student_id)
            safe_student_name = sanitize_filename(student.name)
            student_dir_name = f"{safe_student_id}_{safe_student_name}"
            student_path = f"{exam_dir_name}/{student_dir_name}"

            # 获取该考生的代码列表
            codes = student_codes_map.get(student.id, [])

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

        # 添加导出信息文件
        export_info_path = f"{exam_dir_name}/export_info.txt"
        export_info_content = f"""考试数据导出信息
================

考试名称: {exam.name}
考试科目: {exam.subject}
导出时间: {datetime.now(UTC).isoformat()}
考生数量: {total_students}
代码文件数量: {total_files}

目录结构说明:
- 每个考生一个文件夹，命名格式: {{学号}}_{{姓名}}
- 每个代码文件对应一道题目，命名格式: problem_{{题号}}_{{标题}}.c
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
