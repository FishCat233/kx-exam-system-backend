"""自定义异常类测试."""

from fastapi import status

from app.utils.exceptions import (
    APIException,
    AuthenticationError,
    NotFoundError,
    PermissionDenied,
    ValidationError,
)


class TestAPIException:
    """测试 APIException 基类."""

    def test_api_exception_with_default_params(self):
        """测试使用默认参数创建 APIException."""
        exc = APIException(status_code=500, detail="服务器错误")

        assert exc.status_code == 500
        assert exc.detail == "服务器错误"
        assert exc.headers is None

    def test_api_exception_with_custom_params(self):
        """测试使用自定义参数创建 APIException."""
        headers = {"X-Custom-Header": "value"}
        exc = APIException(status_code=400, detail="请求错误", headers=headers)

        assert exc.status_code == 400
        assert exc.detail == "请求错误"
        assert exc.headers == headers

    def test_api_exception_inheritance(self):
        """测试 APIException 继承自 HTTPException."""
        from fastapi import HTTPException

        exc = APIException(status_code=500, detail="错误")

        assert isinstance(exc, HTTPException)


class TestAuthenticationError:
    """测试 AuthenticationError 认证错误."""

    def test_authentication_error_default_detail(self):
        """测试默认错误详情."""
        exc = AuthenticationError()

        assert exc.status_code == status.HTTP_401_UNAUTHORIZED
        assert exc.detail == "认证失败"
        assert exc.headers == {"WWW-Authenticate": "Bearer"}

    def test_authentication_error_custom_detail(self):
        """测试自定义错误详情."""
        exc = AuthenticationError(detail="Token 已过期")

        assert exc.status_code == status.HTTP_401_UNAUTHORIZED
        assert exc.detail == "Token 已过期"
        assert exc.headers == {"WWW-Authenticate": "Bearer"}

    def test_authentication_error_inheritance(self):
        """测试 AuthenticationError 继承自 APIException."""
        exc = AuthenticationError()

        assert isinstance(exc, APIException)


class TestPermissionDenied:
    """测试 PermissionDenied 权限不足错误."""

    def test_permission_denied_default_detail(self):
        """测试默认错误详情."""
        exc = PermissionDenied()

        assert exc.status_code == status.HTTP_403_FORBIDDEN
        assert exc.detail == "权限不足"
        assert exc.headers is None

    def test_permission_denied_custom_detail(self):
        """测试自定义错误详情."""
        exc = PermissionDenied(detail="需要管理员权限")

        assert exc.status_code == status.HTTP_403_FORBIDDEN
        assert exc.detail == "需要管理员权限"
        assert exc.headers is None

    def test_permission_denied_inheritance(self):
        """测试 PermissionDenied 继承自 APIException."""
        exc = PermissionDenied()

        assert isinstance(exc, APIException)


class TestNotFoundError:
    """测试 NotFoundError 资源不存在错误."""

    def test_not_found_error_default_detail(self):
        """测试默认错误详情."""
        exc = NotFoundError()

        assert exc.status_code == status.HTTP_404_NOT_FOUND
        assert exc.detail == "资源不存在"
        assert exc.headers is None

    def test_not_found_error_custom_detail(self):
        """测试自定义错误详情."""
        exc = NotFoundError(detail="考试不存在")

        assert exc.status_code == status.HTTP_404_NOT_FOUND
        assert exc.detail == "考试不存在"
        assert exc.headers is None

    def test_not_found_error_inheritance(self):
        """测试 NotFoundError 继承自 APIException."""
        exc = NotFoundError()

        assert isinstance(exc, APIException)


class TestValidationError:
    """测试 ValidationError 数据验证错误."""

    def test_validation_error_default_detail(self):
        """测试默认错误详情."""
        exc = ValidationError()

        assert exc.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert exc.detail == "数据验证失败"
        assert exc.headers is None

    def test_validation_error_custom_detail(self):
        """测试自定义错误详情."""
        exc = ValidationError(detail="学号格式不正确")

        assert exc.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert exc.detail == "学号格式不正确"
        assert exc.headers is None

    def test_validation_error_inheritance(self):
        """测试 ValidationError 继承自 APIException."""
        exc = ValidationError()

        assert isinstance(exc, APIException)


class TestExceptionAliases:
    """测试异常类别名."""

    def test_bad_request_exception_alias(self):
        """测试 BadRequestException 别名."""
        from app.utils.exceptions import BadRequestException

        assert BadRequestException is ValidationError

    def test_not_found_exception_alias(self):
        """测试 NotFoundException 别名."""
        from app.utils.exceptions import NotFoundException

        assert NotFoundException is NotFoundError

    def test_unauthorized_exception_alias(self):
        """测试 UnauthorizedException 别名."""
        from app.utils.exceptions import UnauthorizedException

        assert UnauthorizedException is AuthenticationError
