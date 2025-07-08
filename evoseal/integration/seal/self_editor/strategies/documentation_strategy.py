"""Strategy for generating and improving documentation."""

import ast
import inspect
import re
from dataclasses import dataclass, field
from typing import Any, Optional, Union

from ..models import EditCriteria, EditOperation, EditSuggestion
from ..utils import DocstringStyle, ParsedDocstring, parse_docstring
from .base_strategy import BaseEditStrategy


@dataclass
class DocumentationConfig:
    """Configuration for the DocumentationStrategy."""

    # General settings
    require_docstrings: bool = True
    require_type_hints: bool = True
    docstring_style: DocstringStyle = DocstringStyle.GOOGLE

    # Docstring sections to require
    require_args_section: bool = True
    require_returns_section: bool = True
    require_examples_section: bool = False
    require_raises_section: bool = False

    # Type hint settings
    check_missing_return_type: bool = True
    check_missing_param_types: bool = True

    # Style settings
    max_line_length: int = 88

    # Custom sections to check for
    custom_sections: list[str] = field(default_factory=list)

    # Ignore patterns (regex)
    ignore_patterns: list[str] = field(default_factory=list)


class DocumentationStrategy(BaseEditStrategy):
    """Strategy for generating and improving code documentation.

    This strategy analyzes code and provides suggestions for:
    - Adding missing docstrings
    - Improving existing docstrings
    - Adding type hints
    - Documenting parameters and return values
    - Adding examples
    """

    def __init__(self, config: Optional[DocumentationConfig] = None, **kwargs: Any) -> None:
        """Initialize the documentation strategy.

        Args:
            config: Configuration for the documentation strategy
            **kwargs: Additional arguments for BaseEditStrategy
        """
        super().__init__(**kwargs)
        self.config = config or DocumentationConfig()
        self._compiled_ignore_patterns = [
            re.compile(pattern) for pattern in self.config.ignore_patterns
        ]

    def evaluate(self, content: str, **kwargs: Any) -> list[EditSuggestion]:
        """Evaluate content for documentation improvements.

        Args:
            content: The content to evaluate
            **kwargs: Additional context (e.g., 'ast_node' for AST node if available)

        Returns:
            List of documentation improvement suggestions
        """
        if not content or not self.enabled:
            return []

        try:
            # Parse the content as a module
            module = ast.parse(content)

            # Get the AST node from kwargs if available
            ast_node = kwargs.get("ast_node")

            # If a specific AST node is provided, only check that node
            if ast_node is not None:
                return self._evaluate_node(ast_node, content)

            # Otherwise, check all relevant nodes in the module
            suggestions = []

            # Check module-level docstring
            if self.config.require_docstrings and not self._has_docstring(module):
                suggestion = self._create_missing_docstring_suggestion(module, content)
                if suggestion is not None:
                    suggestions.append(suggestion)

            # Check all functions and classes
            for node in ast.walk(module):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    if not self._should_skip_node(node, content):
                        suggestions.extend(self._evaluate_node(node, content))

            return suggestions

        except (SyntaxError, ValueError):
            # If we can't parse the content, return an empty list of suggestions
            return []

    def _evaluate_node(self, node: ast.AST, content: str) -> list[EditSuggestion]:
        """Evaluate a single AST node for documentation issues.

        Args:
            node: The AST node to evaluate
            content: The source code content

        Returns:
            List of documentation improvement suggestions with no None values
        """
        from collections.abc import Iterator, Sequence

        # No need to import List as we use built-in list type
        from typing import Any
        from typing import Optional as Opt
        from typing import TypeVar, cast

        # Initialize with explicit type annotation to ensure we only store EditSuggestion
        suggestions: list[EditSuggestion] = []

        # Check for missing docstrings
        if self.config.require_docstrings and not self._has_docstring(node):
            suggestion = self._create_missing_docstring_suggestion(node, content)
            if suggestion is not None:
                suggestions.append(suggestion)

        # Check existing docstring quality
        docstring = self._safe_get_docstring(node)
        if docstring:
            quality_suggestions = self._check_docstring_quality(node, docstring, content)
            if quality_suggestions:
                # We know _check_docstring_quality returns list[EditSuggestion] with no Nones
                suggestions.extend(quality_suggestions)

        # Check type hints
        if self.config.require_type_hints and isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            type_hint_suggestions = self._check_type_hints(node, content)
            if type_hint_suggestions:
                # _check_type_hints is typed to return list[EditSuggestion] with no Nones
                suggestions.extend(type_hint_suggestions)

        # Return a new list to ensure type safety
        return suggestions.copy()

    def _check_function_docstring(
        self,
        node: Union[ast.FunctionDef, ast.AsyncFunctionDef],
        parsed: Any,  # Using Any for parsed docstring as we don't have the exact type
        content: str,
    ) -> list[EditSuggestion]:
        """Check the quality of a function docstring.

        Args:
            node: The function definition node
            parsed: The parsed docstring
            content: The source code content

        Returns:
            List of suggestions for improving the function docstring
        """
        import logging

        suggestions: list[EditSuggestion] = []

        # Check for missing sections
        if hasattr(parsed, "sections"):
            # Check for Args section if function has parameters (excluding self)
            has_params = (
                len([p for p in node.args.args if p.arg != "self"]) > 0
                or node.args.vararg is not None
                or node.args.kwarg is not None
                or len(node.args.kwonlyargs) > 0
                or node.args.kw_defaults
            )

            logging.debug(f"Checking function {node.name} for missing Args section")
            logging.debug(f"Function has params: {has_params}")
            logging.debug(f"Available sections: {getattr(parsed, 'sections', {})}")

            if has_params and "Args" not in parsed.sections:
                logging.debug(f"Creating Args section suggestion for {node.name}")
                # Generate parameter descriptions based on actual parameters
                param_descriptions = []

                # Add regular parameters
                for param in node.args.args:
                    if param.arg != "self":
                        param_type = (
                            f" ({ast.unparse(param.annotation)}) " if param.annotation else " "
                        )
                        param_descriptions.append(
                            f"    {param.arg}:{param_type}Description of {param.arg}"
                        )

                # Add vararg if present
                if node.args.vararg:
                    param_type = (
                        f" ({ast.unparse(node.args.vararg.annotation)}) "
                        if node.args.vararg.annotation
                        else " "
                    )
                    param_descriptions.append(
                        f"    *{node.args.vararg.arg}:{param_type}Variable length argument list"
                    )

                # Add kwarg if present
                if node.args.kwarg:
                    param_type = (
                        f" ({ast.unparse(node.args.kwarg.annotation)}) "
                        if node.args.kwarg.annotation
                        else " "
                    )
                    param_descriptions.append(
                        f"    **{node.args.kwarg.arg}:{param_type}Arbitrary keyword arguments"
                    )

                # Add keyword-only arguments
                for kwarg in node.args.kwonlyargs:
                    param_type = f" ({ast.unparse(kwarg.annotation)}) " if kwarg.annotation else " "
                    param_descriptions.append(
                        f"    {kwarg.arg}:{param_type}Description of {kwarg.arg}"
                    )

                args_content = (
                    "\n".join(param_descriptions)
                    if param_descriptions
                    else "    param: Description of parameter"
                )

                args_suggestion = self._create_missing_section_suggestion(
                    node,
                    "Args",
                    args_content,
                    "Missing 'Args' section in function docstring",
                )
                if args_suggestion is not None:
                    suggestions.append(args_suggestion)
                    logging.debug(f"Added Args section suggestion for {node.name}")

        # Check for return value documentation
        if (
            node.returns
            and "Returns" not in getattr(parsed, "sections", {})
            and "Yields" not in getattr(parsed, "sections", {})
        ):
            return_suggestion = self._create_missing_section_suggestion(
                node,
                "Returns",
                "    Description of return value",
                "Missing 'Returns' section in function docstring",
            )
            if return_suggestion is not None:
                suggestions.append(return_suggestion)

        # Check for examples section
        if "Examples" not in getattr(parsed, "sections", {}):
            example_suggestion = self._create_missing_section_suggestion(
                node,
                "Examples",
                "    >>> result = function_name()",
                "Missing 'Examples' section in function docstring",
            )
            if example_suggestion is not None:
                suggestions.append(example_suggestion)

        return [s for s in suggestions if s is not None]  # Filter out None values

    def _create_missing_param_suggestion(
        self, node: ast.AST, param: Any, docstring: str, content: str
    ) -> Optional[EditSuggestion]:
        """Create a suggestion for a missing parameter documentation.

        Args:
            node: The AST node containing the parameter
            param: The parameter to document (can be inspect.Parameter or str)
            docstring: The existing docstring
            content: The source code content

        Returns:
            An EditSuggestion for adding the missing parameter documentation, or None if not needed
        """
        try:
            import inspect
            from inspect import Parameter

            # Get parameter name and type
            if hasattr(param, "name") and hasattr(param, "annotation"):
                # It's a proper Parameter object
                param_name = param.name
                param_type = str(param.annotation) if param.annotation != Parameter.empty else "Any"
            else:
                # Fallback for string parameters
                param_name = str(param)
                param_type = "Any"

            # Skip special parameters
            if param_name in ("self", "cls"):
                return None

            # Create a description for the parameter
            param_desc = f"{param_name} ({param_type}): Description of {param_name}"

            # Create a new docstring with the missing parameter
            new_docstring = self._update_param_docstring(docstring, param_name, param_desc)

            if new_docstring != docstring:
                return EditSuggestion(
                    operation=EditOperation.REWRITE,
                    criteria=[EditCriteria.DOCUMENTATION, EditCriteria.COMPLETENESS],
                    original_text=docstring,
                    suggested_text=new_docstring,
                    explanation=f"Missing documentation for parameter '{param_name}'",
                    line_number=node.lineno if hasattr(node, "lineno") else 1,
                    metadata={
                        "node_type": type(node).__name__.lower(),
                        "param": param_name,
                        "param_type": param_type,
                    },
                )
        except Exception as e:
            import logging

            logging.debug(f"Error creating missing param suggestion: {e}")

        return None

    def _update_param_docstring(self, docstring: str, param_name: str, param_desc: str) -> str:
        """Update a docstring to include a parameter description.

        Args:
            docstring: The original docstring
            param_name: Name of the parameter to document
            param_desc: Description of the parameter

        Returns:
            Updated docstring with the parameter documentation
        """
        try:
            # Parse the docstring
            parsed = parse_docstring(docstring, self.config.docstring_style)

            # Get the params dictionary safely
            params = getattr(parsed, "params", {})

            # Add or update the parameter description
            params[param_name] = param_desc

            # Update the params attribute if it exists
            if hasattr(parsed, "params"):
                # Use setattr to avoid mypy issues with dynamic attributes
                parsed.params = params

            # Convert back to string
            return parsed.to_string()

        except Exception as e:
            import logging

            logging.debug(f"Error updating parameter docstring: {e}")
            return docstring

    def _create_remove_param_suggestion(
        self, node: ast.AST, param_name: str, docstring: str, content: str
    ) -> Optional[EditSuggestion]:
        """Create a suggestion to remove a parameter that no longer exists.

        Args:
            node: The AST node containing the docstring
            param_name: Name of the parameter to remove
            docstring: The current docstring
            content: The source code content

        Returns:
            An EditSuggestion for removing the parameter, or None if not needed
        """
        try:
            # No need to import Dict

            # Parse the docstring
            parsed = parse_docstring(docstring, self.config.docstring_style)

            # Get the params dictionary safely
            params: dict[str, Any] = getattr(parsed, "params", {})

            # Check if the parameter exists in the docstring
            if param_name not in params:
                return None

            # Create a copy of the params and remove the parameter
            new_params = dict(params)  # Create a copy to avoid modifying the original
            del new_params[param_name]

            # Update the params if the attribute exists
            if hasattr(parsed, "params"):
                # Use setattr to avoid mypy issues with dynamic attributes
                parsed.params = new_params

            # Convert back to string
            new_docstring = parsed.to_string()

            if new_docstring != docstring:
                return EditSuggestion(
                    operation=EditOperation.REWRITE,
                    criteria=[EditCriteria.DOCUMENTATION, EditCriteria.ACCURACY],
                    original_text=docstring,
                    suggested_text=new_docstring,
                    explanation=f"Remove documentation for non-existent parameter '{param_name}'",
                    line_number=node.lineno if hasattr(node, "lineno") else 1,
                    metadata={
                        "node_type": type(node).__name__.lower(),
                        "param": param_name,
                        "action": "remove_param",
                    },
                )

        except Exception as e:
            import logging

            logging.debug(f"Error creating remove param suggestion: {e}")

        return None

    def _check_parameter_documentation(
        self, node: ast.AST, docstring: str, content: str
    ) -> list[EditSuggestion]:
        """Check if all parameters are properly documented.

        Args:
            node: The AST node to check
            docstring: The docstring to check
            content: The source code content

        Returns:
            List of suggestions for improving parameter documentation, with no None values
        """
        from typing import Any, cast

        # No need to import List as we use built-in list type
        # Initialize with explicit type annotation to ensure we only store EditSuggestion
        suggestions: list[EditSuggestion] = []

        # Only check functions and methods
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return suggestions

        # Get the function signature
        try:
            import inspect

            # Get the function parameters using ast instead of eval
            if hasattr(node, "name") and hasattr(node, "args"):
                # Create a signature from the AST node
                parameters = []

                # Helper function to get parameter annotation
                def get_annotation(arg_node):
                    if hasattr(arg_node, 'annotation'):
                        return self._get_annotation_string(arg_node.annotation)
                    return inspect.Parameter.empty

                # Handle positional-only arguments
                for arg in node.args.posonlyargs:
                    parameters.append(
                        inspect.Parameter(
                            arg.arg,
                            inspect.Parameter.POSITIONAL_ONLY,
                            annotation=get_annotation(arg),
                            default=inspect.Parameter.empty,
                        )
                    )

                # Handle positional-or-keyword arguments
                for arg in node.args.args:
                    parameters.append(
                        inspect.Parameter(
                            arg.arg,
                            inspect.Parameter.POSITIONAL_OR_KEYWORD,
                            annotation=get_annotation(arg),
                            default=inspect.Parameter.empty,
                        )
                    )

                # Handle vararg (e.g., *args)
                if node.args.vararg:
                    parameters.append(
                        inspect.Parameter(
                            node.args.vararg.arg,
                            inspect.Parameter.VAR_POSITIONAL,
                            annotation=get_annotation(node.args.vararg),
                        )
                    )

                # Handle keyword-only arguments
                for arg, default_expr in zip(node.args.kwonlyargs, node.args.kw_defaults or []):
                    # Get the default value if it exists
                    default = (
                        default_expr.value
                        if default_expr and isinstance(default_expr, ast.Constant)
                        else inspect.Parameter.empty
                    )

                    parameters.append(
                        inspect.Parameter(
                            arg.arg,
                            inspect.Parameter.KEYWORD_ONLY,
                            default=default,
                            annotation=get_annotation(arg),
                        )
                    )

                # Handle kwarg (e.g., **kwargs)
                if node.args.kwarg:
                    parameters.append(
                        inspect.Parameter(
                            node.args.kwarg.arg,
                            inspect.Parameter.VAR_KEYWORD,
                            annotation=get_annotation(node.args.kwarg),
                        )
                    )

                # Create the signature
                sig = inspect.Signature(parameters=parameters)
            else:
                sig = None

            # Parse the docstring
            parsed = parse_docstring(docstring, self.config.docstring_style)

            # Get documented parameters from the parsed docstring
            doc_params: dict[str, Any] = getattr(parsed, "params", {})

            # Check for missing parameter documentation
            for param_name, param in sig.parameters.items():
                if param_name in ("self", "cls"):
                    continue  # Skip self/cls parameters

                if param_name not in doc_params:
                    # Create a suggestion for the missing parameter documentation
                    suggestion = self._create_missing_param_suggestion(
                        node, param, docstring, content
                    )
                    if suggestion is not None:
                        suggestions.append(suggestion)

            # Check for parameters that are documented but don't exist in the signature
            for doc_param in list(
                doc_params.keys()
            ):  # Create a list to avoid modifying during iteration
                if doc_param not in sig.parameters:
                    suggestion = self._create_remove_param_suggestion(
                        node, doc_param, docstring, content
                    )
                    if suggestion is not None:
                        suggestions.append(suggestion)

        except Exception as e:
            # Log the error but don't fail the entire analysis
            import logging

            logging.debug(f"Error checking parameter documentation: {e}")

        # Return a new list to ensure type safety
        return suggestions.copy()

    def _should_skip_node(self, node: ast.AST, content: str) -> bool:
        """Determine if a node should be skipped based on ignore patterns."""
        if not hasattr(node, "name") or not node.name:
            return False

        # Skip private methods (except __init__)
        if node.name.startswith("_") and node.name != "__init__":
            return True

        # Skip test methods
        if node.name.startswith("test_"):
            return True

        # Check against ignore patterns
        node_text = ast.get_source_segment(content, node) or ""
        for pattern in self._compiled_ignore_patterns:
            if pattern.search(node_text) or pattern.search(node.name):
                return True

        return False

    def _has_docstring(self, node: ast.AST) -> bool:
        """Check if a node has a docstring."""
        if not hasattr(node, "body") or not node.body:
            return False

        first = node.body[0]
        return (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        )

    def _create_missing_docstring_suggestion(
        self, node: ast.AST, content: str
    ) -> Optional[EditSuggestion]:
        """Create a suggestion for a missing docstring.

        Args:
            node: The AST node to document
            content: The source code content

        Returns:
            An EditSuggestion with the proposed docstring, or None if not applicable
        """
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return self._create_missing_function_docstring(node, content)
        elif isinstance(node, ast.ClassDef):
            return self._create_missing_class_docstring(node, content)
        elif isinstance(node, ast.Module):
            return self._create_missing_module_docstring(node, content)
        return None

    def _create_missing_function_docstring(
        self, node: Union[ast.FunctionDef, ast.AsyncFunctionDef], content: str
    ) -> EditSuggestion:
        """Create a suggestion for a missing function docstring.

        Args:
            node: The function definition node
            content: The source code content

        Returns:
            An EditSuggestion with the proposed function docstring
        """
        # Generate a docstring based on the function signature
        docstring = self._generate_function_docstring(node)

        # Find where to insert the docstring
        lines = content.splitlines()
        start_line = node.lineno - 1  # Convert to 0-based

        # Find the end of the function signature
        insert_line = start_line + 1
        while insert_line < len(lines) and not lines[insert_line].strip().startswith(":"):
            insert_line += 1

        if insert_line < len(lines):
            insert_line += 1  # Move past the colon line

        # Get indentation
        indent = self._get_indent(lines[start_line])

        # Format the docstring with proper indentation
        docstring_lines = [f'{indent}"""{docstring}']
        docstring_lines.append(f'{indent}"""')
        docstring_text = "\n".join(docstring_lines)

        return EditSuggestion(
            operation=EditOperation.ADD,
            criteria=[EditCriteria.DOCUMENTATION, EditCriteria.COMPLETENESS],
            original_text="",
            suggested_text=docstring_text,
            explanation=f"Missing docstring for function '{node.name}'",
            line_number=insert_line + 1,  # Convert back to 1-based
            metadata={"node_type": "function", "node_name": node.name},
        )

    def _create_missing_class_docstring(self, node: ast.ClassDef, content: str) -> EditSuggestion:
        """Create a suggestion for a missing class docstring."""
        docstring = f"{node.name} class."

        lines = content.splitlines()
        start_line = node.lineno - 1  # Convert to 0-based

        # Find where to insert the docstring (after the class definition)
        insert_line = start_line + 1
        while insert_line < len(lines) and not lines[insert_line].strip().startswith(":"):
            insert_line += 1

        if insert_line < len(lines):
            insert_line += 1  # Move past the colon line

        # Get indentation
        indent = self._get_indent(lines[start_line])

        # Format the docstring with proper indentation
        docstring_lines = [f'{indent}"""{docstring}']
        docstring_lines.append(f'{indent}"""')
        docstring_text = "\n".join(docstring_lines)

        return EditSuggestion(
            operation=EditOperation.ADD,
            criteria=[EditCriteria.DOCUMENTATION, EditCriteria.COMPLETENESS],
            original_text="",
            suggested_text=docstring_text,
            explanation=f"Missing docstring for class '{node.name}'",
            line_number=insert_line + 1,  # Convert back to 1-based
            metadata={"node_type": "class", "node_name": node.name},
        )

    def _create_missing_module_docstring(
        self, node: ast.Module, content: str
    ) -> Optional[EditSuggestion]:
        """Create a suggestion for a missing module docstring.

        Args:
            node: The module node
            content: The source code content

        Returns:
            An EditSuggestion with the proposed module docstring, or None if not applicable
        """
        docstring = "Module docstring."

        lines = content.splitlines()
        insert_line = 0

        # Skip shebang and encoding
        if lines and (lines[0].startswith("#!") or lines[0].startswith("# -*-")):
            insert_line = 1

        # Skip any other comments at the top
        while insert_line < len(lines) and lines[insert_line].strip().startswith("#"):
            insert_line += 1

        # If there's a docstring right after, don't add another one
        if insert_line < len(lines) and (
            lines[insert_line].strip().startswith('"""')
            or lines[insert_line].strip().startswith("'" * 3)
            or lines[insert_line].strip().startswith('r"""')
            or lines[insert_line].strip().startswith("r'''")
        ):
            return None

        # Get indentation
        indent = ""
        if insert_line < len(lines):
            indent_match = re.match(r"^\s*", lines[insert_line])
            if indent_match:
                indent = indent_match.group(0)

        # Format the docstring
        docstring_lines = [f'{indent}"""{docstring}']
        docstring_lines.append(f'{indent}"""')
        docstring_text = "\n".join(docstring_lines)

        return EditSuggestion(
            operation=EditOperation.ADD,
            criteria=[EditCriteria.DOCUMENTATION, EditCriteria.COMPLETENESS],
            original_text="",
            suggested_text=docstring_text,
            explanation="Missing module docstring",
            line_number=insert_line + 1,  # Convert to 1-based
            metadata={"node_type": "module"},
        )

    def _safe_get_docstring(self, node: ast.AST) -> Optional[str]:
        """Safely get docstring from an AST node."""
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef, ast.ClassDef, ast.Module)):
            return ast.get_docstring(node, clean=False)
        return None

    def _check_class_docstring(
        self, node: ast.ClassDef, parsed: ParsedDocstring, content: str
    ) -> list[EditSuggestion]:
        """Check the quality of a class docstring.

        Args:
            node: The class definition node
            parsed: The parsed docstring
            content: The source code content

        Returns:
            List of suggestions for improving the class docstring
        """
        suggestions: list[EditSuggestion] = []

        # Check for attributes section if the class has attributes
        if "Attributes" not in parsed.sections:
            # Look for class attributes and instance attributes
            has_attributes = any(
                isinstance(n, ast.Assign) and n.targets and isinstance(n.targets[0], ast.Name)
                for n in ast.walk(node)
            )

            if has_attributes:
                attr_suggestion = self._create_missing_section_suggestion(
                    node,
                    "Attributes",
                    "    attribute_name: Description of attribute",
                    "Missing 'Attributes' section in class docstring",
                )
                if attr_suggestion is not None:
                    suggestions.append(attr_suggestion)

        # Check for methods section if the class has methods
        if "Methods" not in parsed.sections:
            has_methods = any(
                isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) for n in node.body
            )

            if has_methods:
                method_suggestion = self._create_missing_section_suggestion(
                    node,
                    "Methods",
                    "    method_name(): Description of method",
                    "Missing 'Methods' section in class docstring",
                )
                if method_suggestion is not None:
                    suggestions.append(method_suggestion)

        return [s for s in suggestions if s is not None]  # Filter out None values

    def _check_docstring_quality(
        self, node: ast.AST, docstring: str, content: str
    ) -> list[EditSuggestion]:
        """Check the quality of an existing docstring.

        Args:
            node: The AST node containing the docstring
            docstring: The docstring to check
            content: The source code content

        Returns:
            List of suggestions for improving the docstring, with no None values
        """
        suggestions: list[EditSuggestion] = []

        try:
            # Parse the docstring
            parsed = parse_docstring(docstring, self.config.docstring_style)

            # Check for empty docstring
            if not parsed.summary.strip():
                suggestions.append(
                    EditSuggestion(
                        operation=EditOperation.REWRITE,
                        criteria=[EditCriteria.DOCUMENTATION, EditCriteria.CLARITY],
                        original_text=docstring,
                        suggested_text='""\n    Docstring here.\n    """',
                        explanation="Empty docstring",
                        line_number=node.lineno + 1 if hasattr(node, "lineno") else 1,
                        metadata={"node_type": type(node).__name__.lower()},
                    )
                )

            # Check docstring quality based on node type
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_suggestions = self._check_function_docstring(node, parsed, content)
                if func_suggestions:
                    # _check_function_docstring is typed to return list[EditSuggestion] with no Nones
                    suggestions.extend(func_suggestions)
            elif isinstance(node, ast.ClassDef):
                class_suggestions = self._check_class_docstring(node, parsed, content)
                if class_suggestions:
                    # _check_class_docstring is typed to return list[EditSuggestion] with no Nones
                    suggestions.extend(class_suggestions)

            # Check parameter documentation
            param_suggestions = self._check_parameter_documentation(node, docstring, content)
            if param_suggestions:
                # _check_parameter_documentation is typed to return list[EditSuggestion] with no Nones
                suggestions.extend(param_suggestions)

            # Check line length in docstring
            for i, line in enumerate(docstring.split("\n")):
                if len(line) > self.config.max_line_length:
                    suggestions.append(
                        EditSuggestion(
                            operation=EditOperation.REWRITE,
                            criteria=[EditCriteria.DOCUMENTATION, EditCriteria.STYLE],
                            original_text=line,
                            suggested_text=line[: self.config.max_line_length],
                            explanation=(
                                f"Docstring line too long ({len(line)} > "
                                f"{self.config.max_line_length} characters)"
                            ),
                            line_number=(node.lineno + i + 1 if hasattr(node, "lineno") else i + 1),
                            metadata={
                                "node_type": type(node).__name__.lower(),
                                "line_length": len(line),
                                "max_line_length": self.config.max_line_length,
                            },
                        )
                    )

        except Exception as e:
            # Log the error but don't fail the entire analysis
            import logging

            logging.debug(f"Error checking docstring quality: {e}")

        # Ensure we're returning list[EditSuggestion] with no None values
        return [s for s in suggestions if s is not None]

    def _create_missing_section_suggestion(
        self, node: ast.AST, section_name: str, section_content: str, explanation: str
    ) -> Optional[EditSuggestion]:
        """Create a suggestion for a missing docstring section.

        Args:
            node: The AST node with the docstring
            section_name: Name of the missing section
            section_content: Example content for the section
            explanation: Explanation of why the section is needed

        Returns:
            An EditSuggestion for adding the missing section, or None if not applicable
        """
        # Get the existing docstring
        docstring = self._safe_get_docstring(node)
        if not docstring:
            return None

        try:
            # Create the new docstring with the missing section
            parsed = parse_docstring(docstring, self.config.docstring_style)

            # Add the missing section
            parsed.sections[section_name] = section_content

            # Convert back to string
            new_docstring = parsed.to_string()

            # Format with triple quotes
            lines = ['"""' + new_docstring]
            lines.append('"""')
            new_docstring = "\n".join(lines)

            # Get the indentation
            node_text = ast.get_source_segment(self._get_source(node), node)
            indent = self._get_indent(node_text or "")

            # Apply indentation
            new_docstring = "\n".join(
                (indent + line) if line.strip() else "" for line in new_docstring.split("\n")
            )

            return EditSuggestion(
                operation=EditOperation.REWRITE,
                criteria=[EditCriteria.DOCUMENTATION, EditCriteria.COMPLETENESS],
                original_text=docstring,
                suggested_text=new_docstring,
                explanation=explanation,
                line_number=node.lineno + 1 if hasattr(node, "lineno") else 1,
                metadata={
                    "node_type": type(node).__name__.lower(),
                    "section": section_name,
                    "file": getattr(self, "_current_file", "unknown"),
                    "node_name": getattr(node, "name", "unknown"),
                },
            )
        except Exception as e:
            import logging

            logging.debug(f"Failed to create section suggestion: {e}")
            return None

    def _check_type_hints(
        self, node: Union[ast.FunctionDef, ast.AsyncFunctionDef], content: str
    ) -> list[EditSuggestion]:
        """Check for missing type hints in function parameters and return type."""
        suggestions = []

        # Check return type annotation
        if self.config.check_missing_return_type and node.returns is None:
            suggestions.append(
                self._create_missing_type_hint_suggestion(
                    node,
                    "return",
                    f"Return type hint is missing for function '{node.name}'",
                )
            )

        # Check parameter type annotations
        if self.config.check_missing_param_types:
            for arg in node.args.args:
                if arg.arg != "self" and arg.annotation is None:
                    suggestions.append(
                        self._create_missing_type_hint_suggestion(
                            node,
                            f"parameter '{arg.arg}'",
                            f"Type hint for parameter '{arg.arg}' is missing in function '{node.name}'",
                        )
                    )

        return suggestions

    def _create_missing_type_hint_suggestion(
        self, node: ast.AST, location: str, message: str
    ) -> EditSuggestion:
        """Create a suggestion for a missing type hint."""
        return EditSuggestion(
            operation=EditOperation.ADD,
            criteria=[EditCriteria.DOCUMENTATION, EditCriteria.CLARITY],
            original_text="",
            suggested_text="",  # This would be filled in by the apply method
            explanation=message,
            line_number=node.lineno if hasattr(node, "lineno") else 1,
            metadata={
                "type_hint_location": location,
                "node_type": type(node).__name__.lower(),
            },
        )

    def _generate_function_docstring(
        self, node: Union[ast.FunctionDef, ast.AsyncFunctionDef]
    ) -> str:
        """Generate a docstring for a function."""
        docstring = [f"{node.name}."]

        # Add a blank line after the summary
        docstring.append("")

        # Add Args section if there are parameters
        args = [arg for arg in node.args.args if arg.arg != "self"]
        if args:
            docstring.append("Args:")
            for arg in args:
                arg_type = f": {ast.unparse(arg.annotation)}" if arg.annotation else ""
                docstring.append(f"    {arg.arg}{arg_type}: Description of {arg.arg}")

        # Add Returns section if there's a return type or return statement
        has_return = any(isinstance(n, ast.Return) for n in ast.walk(node))
        if node.returns or has_return:
            docstring.append("")
            docstring.append("Returns:")
            return_type = f" {ast.unparse(node.returns)}" if node.returns else ""
            docstring.append(f"    {return_type}: Description of return value")

        # Add Examples section if enabled
        if self.config.require_examples_section:
            docstring.append("")
            docstring.append("Examples:")
            docstring.append(f"    >>> result = {node.name}()")

        return "\n".join(docstring)

    def _generate_args_section(self, node: Union[ast.FunctionDef, ast.AsyncFunctionDef]) -> str:
        """Generate the Args section for a function docstring."""
        args = [arg for arg in node.args.args if arg.arg != "self"]
        if not args and not node.args.vararg and not node.args.kwarg:
            return ""

        lines = ["    Args:"]
        for arg in args:
            arg_type = f": {ast.unparse(arg.annotation)}" if arg.annotation else ""
            lines.append(f"        {arg.arg}{arg_type}: Description of {arg.arg}")
        return "\n".join(lines)

    def _get_source(self, node: ast.AST) -> str:
        """Get the source code for an AST node.

        This is a simplified version - in a real implementation, you'd want to
        get the source from the original file or a source map
        """
        return ast.unparse(node)

    def _get_indent(self, line: str) -> str:
        """Get the indentation of a line.

        Args:
            line: The line to get indentation from (can be empty)

        Returns:
            The indentation string (whitespace)
        """
        if not line:
            return ""
        match = re.match(r"^\s*", line)
        return match.group(0) if match else ""

    def get_config(self) -> dict[str, Any]:
        """Get the strategy configuration."""
        return {
            "require_docstrings": self.config.require_docstrings,
            "require_type_hints": self.config.require_type_hints,
            "docstring_style": self.config.docstring_style.value,
            "require_args_section": self.config.require_args_section,
            "require_returns_section": self.config.require_returns_section,
            "require_examples_section": self.config.require_examples_section,
            "require_raises_section": self.config.require_raises_section,
            "check_missing_return_type": self.config.check_missing_return_type,
            "check_missing_param_types": self.config.check_missing_param_types,
            "max_line_length": self.config.max_line_length,
            "custom_sections": self.config.custom_sections,
            "ignore_patterns": self.config.ignore_patterns,
        }
