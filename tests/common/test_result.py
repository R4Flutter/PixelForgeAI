from __future__ import annotations

from common.result import Result, Success, Failure


class TestResult:
    def test_success_creation(self) -> None:
        result: Result[str, str] = Success("ok")
        assert result.is_success

    def test_failure_creation(self) -> None:
        result: Result[str, str] = Failure("error")
        assert not result.is_success

    def test_success_map(self) -> None:
        result: Result[int, str] = Success(42)
        mapped = result.map(lambda x: x * 2)
        assert mapped.is_success

    def test_failure_map(self) -> None:
        result: Result[int, str] = Failure("fail")
        mapped = result.map(lambda x: x * 2)
        assert not mapped.is_success

    def test_success_bind(self) -> None:
        result: Result[int, str] = Success(10)
        bound = result.bind(lambda x: Success(x + 5))
        assert bound.is_success

    def test_failure_bind(self) -> None:
        result: Result[int, str] = Failure("fail")
        bound = result.bind(lambda x: Success(x + 5))
        assert not bound.is_success

    def test_unwrap_success(self) -> None:
        result: Result[str, str] = Success("value")
        assert result.unwrap() == "value"

    def test_unwrap_or_success(self) -> None:
        result: Result[str, str] = Success("value")
        assert result.unwrap_or("default") == "value"

    def test_unwrap_or_failure(self) -> None:
        result: Result[str, str] = Failure("error")
        assert result.unwrap_or("default") == "default"
