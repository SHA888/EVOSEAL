"""
Mock implementation of SelfEditor for testing purposes.
"""

from typing import Any, Dict, List, Optional


class MockSelfEditor:
    """Mock implementation of SelfEditor for testing."""

    async def suggest_edits(
        self,
        prompt: str,
        response: str,
        knowledge: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None,
        **kwargs,  # Accept any additional kwargs
    ) -> List[Dict[str, Any]]:
        """Mock implementation of suggest_edits."""
        # In a real implementation, this would analyze the response and knowledge
        # to suggest improvements
        if not isinstance(prompt, str) or not isinstance(response, str):
            return []

        if "capital" in prompt.lower() and "france" in prompt.lower():
            return [
                {
                    "type": "fact_verification",
                    "description": "Verify the capital of France",
                    "confidence": 0.9,
                    "suggestion": "Paris is the capital of France.",
                }
            ]

        # Return a default edit suggestion for other prompts
        return [{"type": "clarification", "description": "Added context", "confidence": 0.8}]

    async def apply_edit(
        self,
        text: str,
        edit_suggestion: Dict[str, Any],
        **kwargs,  # Accept context and any other kwargs
    ) -> str:
        """Mock implementation of apply_edit."""
        if not isinstance(text, str) or not isinstance(edit_suggestion, dict):
            return text

        # In a real implementation, this would apply the suggested edit to the text
        if edit_suggestion.get("type") == "fact_verification":
            return f"{text} (Verified: {edit_suggestion.get('suggestion', '')})"
        elif edit_suggestion.get("type") == "clarification":
            return f"{text} [edited: {edit_suggestion.get('description', 'clarification')}]"
        return text
