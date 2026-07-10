from __future__ import annotations

from domain.rules.naming_rules import NamingRules
from domain.rules.processing_rules import ProcessingRules


class TestNamingRules:
    def test_generate_output_name_with_suffix(self) -> None:
        rules = NamingRules()
        name = rules.generate_output_name("test.png", suffix="_processed")
        assert "_processed" in name

    def test_generate_output_name_preserves_extension(self) -> None:
        rules = NamingRules()
        name = rules.generate_output_name("photo.jpg", suffix="_final")
        assert name.endswith(".jpg")


class TestProcessingRules:
    def test_max_dimensions(self) -> None:
        rules = ProcessingRules()
        assert rules.max_width == 8192
        assert rules.max_height == 8192
