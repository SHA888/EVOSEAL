"""Tests for the SecurityAnalysisStrategy class."""
import ast
import pytest
from unittest.mock import MagicMock

from evoseal.integration.seal.self_editor.strategies.security_analysis_strategy import (
    SecurityAnalysisStrategy, SecurityConfig, SecurityIssueSeverity
)
from evoseal.integration.seal.self_editor.models import EditSuggestion, EditOperation, EditCriteria


class TestSecurityAnalysisStrategy:
    """Test cases for SecurityAnalysisStrategy."""
    
    @pytest.fixture
    def config(self):
        """Return a default SecurityConfig for testing."""
        return SecurityConfig()
    
    @pytest.fixture
    def strategy(self, config):
        """Return a SecurityAnalysisStrategy instance for testing."""
        return SecurityAnalysisStrategy(config=config)
    
    def test_initialization(self, config):
        """Test that the strategy initializes correctly."""
        strategy = SecurityAnalysisStrategy(config=config)
        assert strategy.config == config
        assert strategy.priority == 10  # Higher priority than documentation/formatting
    
    def test_evaluate_disabled_strategy(self, config):
        """Test that disabled strategy returns no suggestions."""
        config.enabled = False
        strategy = SecurityAnalysisStrategy(config=config)
        suggestions = strategy.evaluate("import os\nos.system('ls -la')")
        assert len(suggestions) == 0
    
    def test_check_risky_imports(self, strategy):
        """Test detection of risky imports."""
        content = """
import os
import sys
from os import system

result = system('ls -la')
"""
        suggestions = strategy.evaluate(content)
        
        # Should find the risky import (os module and/or system import)
        assert len(suggestions) >= 1
        
        # Check for either the os import or the system import being flagged
        has_os_import = any("import os" in str(s.original_text) for s in suggestions)
        has_system_import = any("from os import system" in str(s.original_text) for s in suggestions)
        assert has_os_import or has_system_import, \
            f"Expected to find either 'import os' or 'from os import system' in suggestions, but got: {suggestions}"
    
    def test_check_unsafe_functions(self, strategy):
        """Test detection of unsafe function calls."""
        content = """
def example():
    eval('1 + 1')
    exec('print(1)')
"""
        suggestions = strategy.evaluate(content)
        
        # Should find eval and exec calls
        assert len(suggestions) >= 2
        assert any("eval(" in str(s.original_text) for s in suggestions)
        assert any("exec(" in str(s.original_text) for s in suggestions)
    
    def test_check_sql_injection(self, strategy):
        """Test detection of SQL injection vulnerabilities."""
        content = """
import sqlite3

def get_user(username):
    conn = sqlite3.connect('example.db')
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM users WHERE username = '{username}'")
    return cursor.fetchone()
"""
        suggestions = strategy.evaluate(content)
        
        # Should find SQL injection vulnerability
        assert len(suggestions) >= 1
        assert any("SQL injection" in s.explanation for s in suggestions)
    
    def test_check_xss(self, strategy):
        """Test detection of XSS vulnerabilities."""
        content = """
from flask import Flask, request

app = Flask(__name__)

@app.route('/search')
def search():
    query = request.args.get('q', '')
    return f'<h1>Results for: {query}</h1>'  # Potential XSS
"""
        suggestions = strategy.evaluate(content)
        
        # Should find XSS vulnerability
        assert len(suggestions) >= 1
        assert any("XSS" in s.explanation for s in suggestions)
    
    def test_check_command_injection(self, strategy):
        """Test detection of command injection vulnerabilities."""
        content = """
import os

def list_directory(directory):
    os.system(f'ls -la {directory}')  # Potential command injection
"""
        suggestions = strategy.evaluate(content)
        
        # Should find command injection vulnerability
        assert len(suggestions) >= 1
        assert any("command injection" in s.explanation.lower() for s in suggestions)
    
    def test_check_file_operations(self, strategy):
        """Test detection of unsafe file operations."""
        content = """
def read_file(filename):
    with open(filename, 'r') as f:  # Potential path traversal
        return f.read()
"""
        suggestions = strategy.evaluate(content)
        
        # Should find unsafe file operation
        assert len(suggestions) >= 1
        assert any("file path" in s.explanation.lower() for s in suggestions)
    
    def test_check_hardcoded_secrets(self, strategy):
        """Test detection of hardcoded secrets."""
        content = """
# Hardcoded credentials
DB_PASSWORD = "s3cr3t_p@ssw0rd!"
API_KEY = "12345-abcde-67890-fghij"
"""
        suggestions = strategy.evaluate(content)
        
        # Should find hardcoded secrets
        assert len(suggestions) >= 2
        assert any("password" in s.explanation.lower() for s in suggestions)
        assert any("api" in s.explanation.lower() for s in suggestions)
    
    def test_ignore_patterns(self):
        """Test that ignore patterns work correctly."""
        config = SecurityConfig(ignore_patterns=[r'# no-sec'])
        strategy = SecurityAnalysisStrategy(config=config)
        
        # This would normally trigger a security warning
        content = """
# no-sec
DB_PASSWORD = "s3cr3t_p@ssw0rd!"  # no-sec
"""
        suggestions = strategy.evaluate(content)
        
        # Should be ignored due to the comment
        assert len(suggestions) == 0
    
    def test_custom_checks(self):
        """Test that custom security checks work."""
        def custom_check(content, **kwargs):
            return [
                EditSuggestion(
                    operation=EditOperation.REWRITE,
                    criteria=[EditCriteria.SECURITY],
                    original_text=content.split('\n')[0],
                    suggested_text="# CUSTOM CHECK: " + content.split('\n')[0],
                    explanation="Custom security check failed",
                    confidence=1.0,
                    line_number=1
                )
            ]
        
        config = SecurityConfig(custom_checks=[custom_check])
        strategy = SecurityAnalysisStrategy(config=config)
        
        content = "some_code()"
        suggestions = strategy.evaluate(content)
        
        # Should include the custom check result
        assert len(suggestions) >= 1
        assert any("CUSTOM CHECK" in s.suggested_text for s in suggestions)
    
    def test_get_config(self, strategy):
        """Test that get_config returns the expected structure."""
        config = strategy.get_config()
        
        assert isinstance(config, dict)
        assert 'enabled' in config
        assert 'check_risky_imports' in config
        assert 'check_hardcoded_secrets' in config
        assert 'ignore_patterns' in config
