"""Unit tests for CodeStyleStrategy."""
import pytest

from evoseal.integration.seal.self_editor.strategies.code_style_strategy import CodeStyleStrategy
from evoseal.integration.seal.self_editor.models import EditOperation, EditCriteria


class TestCodeStyleStrategy:
    """Test suite for CodeStyleStrategy."""
    
    @pytest.fixture
    def strategy(self):
        """Create a CodeStyleStrategy instance for testing."""
        return CodeStyleStrategy(max_line_length=80, indent_size=4, use_spaces=True)
    
    def test_line_length_violation(self, strategy):
        """Test detection of lines that are too long."""
        content = """def example():
    # This line is way too long and should trigger the line length check because it exceeds the maximum allowed characters.
    pass"""
        
        suggestions = strategy.evaluate(content)
        assert len(suggestions) == 1
        assert suggestions[0].operation == EditOperation.REWRITE
        assert "too long" in suggestions[0].explanation
        assert EditCriteria.STYLE in suggestions[0].criteria
        assert EditCriteria.READABILITY in suggestions[0].criteria
    
    def test_trailing_whitespace(self, strategy):
        """Test detection of trailing whitespace."""
        content = "def example():    \n    pass"
        
        suggestions = strategy.evaluate(content)
        assert len(suggestions) == 1
        assert suggestions[0].operation == EditOperation.REMOVE
        assert "trailing whitespace" in suggestions[0].explanation
    
    def test_mixed_indentation(self):
        """Test detection of mixed indentation."""
        # Create a strategy that prefers spaces
        strategy = CodeStyleStrategy(use_spaces=True)
        content = "def example():\n \t# This line has mixed indentation\n    pass"
        
        suggestions = strategy.evaluate(content)
        assert len(suggestions) == 1
        assert "mixed indentation" in suggestions[0].explanation
    
    def test_quote_consistency(self, strategy):
        """Test detection of inconsistent quote usage."""
        content = """message = 'Hello, World!'
name = "John Doe"
"""
        suggestions = strategy.evaluate(content)
        assert any("Mixed single and double quotes" in s.explanation for s in suggestions)
    
    def test_apply_suggestion(self, strategy):
        """Test applying a suggestion to content."""
        content = "def example():    \n    pass"
        suggestions = strategy.evaluate(content)
        
        # Apply the first suggestion (trailing whitespace removal)
        if suggestions:
            result = strategy.apply(content, suggestions[0])
            assert result == "def example():\n    pass"
    
    def test_disabled_strategy(self):
        """Test that disabled strategy returns no suggestions."""
        strategy = CodeStyleStrategy(enabled=False)
        content = "def example():    \n    pass"
        assert not strategy.evaluate(content)
    
    def test_get_config(self, strategy):
        """Test getting strategy configuration."""
        config = strategy.get_config()
        assert config['strategy_name'] == 'CodeStyleStrategy'
        assert config['max_line_length'] == 80
        assert config['indent_size'] == 4
        assert config['use_spaces'] is True
        assert config['enabled'] is True
