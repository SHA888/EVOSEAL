"""Tests for the SEAL (Self-Adapting Language Models) prompt templates and construction."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from evoseal.integration.seal.prompt import (
    BASE_TEMPLATES,
    DEFAULT_TEMPLATES,
    DOMAIN_TEMPLATES,
    SYSTEM_TEMPLATES,
    PromptConstructor,
    PromptStyle,
    PromptTemplate,
)


class TestPromptTemplates:
    """Test the default prompt templates and template management."""

    def test_default_templates_loaded(self):
        """Test that default templates are loaded correctly."""
        # Check that we have templates from all categories
        assert len(DEFAULT_TEMPLATES) > 0
        assert len(BASE_TEMPLATES) > 0
        assert len(DOMAIN_TEMPLATES) > 0
        assert len(SYSTEM_TEMPLATES) > 0

        # Check that all templates are valid
        for name, template in DEFAULT_TEMPLATES.items():
            # Check if the value is a PromptTemplate (from either module)
            if hasattr(template, "name") and hasattr(template, "template"):
                assert template.name == name
                assert template.template.strip() != ""
            # Or a tuple of (template_str, description)
            elif isinstance(template, tuple):
                template_str, _ = template
                assert isinstance(template_str, str)
                assert template_str.strip() != ""
            else:
                # For any other case, fail the test
                assert (
                    False
                ), f"Unexpected template type: {type(template)} for template {name}"

    @pytest.mark.parametrize(
        "style",
        ["base_instruction", "base_chat", "base_completion", "base_chain_of_thought"],
    )
    def test_base_templates(self, style):
        """Test that base templates have the expected structure."""
        template = DEFAULT_TEMPLATES[style]
        assert "{knowledge}" in template.template
        assert "{user_input}" in template.template or "{question}" in template.template

    @pytest.mark.parametrize(
        "domain",
        [
            "code_generation",
            "code_explanation",
            "documentation",
        ],
    )
    def test_domain_templates(self, domain):
        """Test that domain-specific templates are properly structured."""
        template = DEFAULT_TEMPLATES[domain]
        assert "{knowledge}" in template.template
        assert "{user_input}" in template.template

    def test_system_templates(self):
        """Test that system message templates are properly structured."""
        for name in SYSTEM_TEMPLATES.keys():
            template = DEFAULT_TEMPLATES[f"system_{name}"]
            assert template.style == "SYSTEM"
            assert len(template.required_fields) == 0


class TestPromptIntegration:
    """Integration tests for prompt construction with templates."""

    @pytest.fixture
    def prompt_constructor(self):
        """Create a PromptConstructor with default templates."""
        return PromptConstructor()

    @pytest.fixture
    def sample_knowledge(self):
        """Sample knowledge for testing."""
        return [
            {
                "content": "Python is a high-level programming language.",
                "source": "general",
            },
            {"content": "Python uses indentation for code blocks.", "source": "syntax"},
        ]

    @pytest.mark.asyncio
    async def test_construct_with_template(self, prompt_constructor, sample_knowledge):
        """Test constructing a prompt with a specific template."""
        # Register a test template
        prompt_constructor.add_template(
            "test_template",
            "Test template: {user_input}\nContext: {knowledge}",
            "INSTRUCTION",
            "A test template",
            {"user_input", "knowledge"},
        )

        # Construct a prompt
        result = prompt_constructor.create_prompt(
            "test_template", user_input="What is Python?", knowledge=sample_knowledge
        )

        # Verify the result
        assert "Test template: What is Python?" in result
        assert "Context:" in result
        assert "Python is a high-level programming language" in result

    @pytest.mark.parametrize(
        "template_name,expected_style",
        [
            ("base_instruction", "INSTRUCTION"),
            ("base_chat", "CHAT"),
            ("code_generation", "INSTRUCTION"),
        ],
    )
    def test_template_styles(self, template_name, expected_style):
        """Test that templates have the correct styles."""
        template = DEFAULT_TEMPLATES[template_name]
        assert template.style == expected_style

    def test_template_validation(self):
        """Test that template validation works as expected."""
        # Should raise error for missing required fields
        with pytest.raises(ValueError):
            PromptTemplate(
                name="invalid",
                template="Missing required fields",
                description="Invalid template",
                style="INSTRUCTION",
                required_fields={"missing_field"},
            )


class TestPromptCaching:
    """Test caching functionality for prompt templates."""

    @pytest.fixture
    def mock_time(self, monkeypatch):
        """Mock time for testing caching."""
        current_time = 1000.0

        def mock_time_func():
            return current_time

        monkeypatch.setattr("time.time", mock_time_func)
        return current_time

    @pytest.mark.asyncio
    async def test_template_caching(self):
        """Test that templates are properly cached."""
        from evoseal.integration.seal.enhanced_seal_system import (
            EnhancedSEALSystem,
            SEALConfig,
        )
        from evoseal.integration.seal.knowledge.knowledge_base import KnowledgeBase
        from evoseal.integration.seal.prompt.constructor import PromptTemplate

        # Create a mock knowledge base
        mock_kb = MagicMock(spec=KnowledgeBase)
        mock_kb.search = AsyncMock(return_value=[])

        # Create SEAL system with caching enabled
        config = SEALConfig(
            enable_caching=True,  # This enables all caching, including templates
            cache_ttl_seconds=60,
            max_cache_size=100,
        )
        system = EnhancedSEALSystem(
            config=config,
            knowledge_base=mock_kb,
        )

        # Create a test template
        test_template = PromptTemplate(
            name="test_template",
            template="Test template: {user_input}",
            style="INSTRUCTION",
            description="A test template",
            required_fields={"user_input"},
        )

        # Add the template to the system's prompt constructor
        system.prompt_constructor.add_template(test_template)

        # Manually add the template to the cache
        system._template_cache["test_template"] = test_template

        # Get the template - should be in cache
        template1 = await system._get_cached_template("test_template")
        assert template1 is not None
        assert template1.name == "test_template"

        # Get it again - should be the same object from cache
        template2 = await system._get_cached_template("test_template")
        assert template2 is template1

        # Clear the cache and get a fresh template
        system._template_cache.clear()

        # Create a new template with the same name but different content
        new_template = PromptTemplate(
            name="test_template",
            template="New template: {user_input}",
            style="INSTRUCTION",
            description="A new test template",
            required_fields={"user_input"},
        )

        # Replace the template in the constructor
        system.prompt_constructor.templates["test_template"] = new_template

        # Clear the cache again to ensure we get the new template
        system._template_cache.clear()

        # This should get the new template
        template3 = await system._get_cached_template("test_template")
        assert template3 is not None
        assert template3.name == "test_template"
        assert "New template" in template3.template
        assert template3.template == "New template: {user_input}"
