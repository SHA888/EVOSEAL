"""Strategy for generating and improving documentation."""
import ast
import inspect
import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set, Tuple, Union

from ..models import EditSuggestion, EditOperation, EditCriteria
from ..utils import DocstringStyle, parse_docstring, ParsedDocstring
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
    custom_sections: List[str] = field(default_factory=list)
    
    # Ignore patterns (regex)
    ignore_patterns: List[str] = field(default_factory=list)


class DocumentationStrategy(BaseEditStrategy):
    """Strategy for generating and improving code documentation.
    
    This strategy analyzes code and provides suggestions for:
    - Adding missing docstrings
    - Improving existing docstrings
    - Adding type hints
    - Documenting parameters and return values
    - Adding examples
    """
    
    def __init__(self, config: Optional[DocumentationConfig] = None, **kwargs):
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
    
    def evaluate(self, content: str, **kwargs) -> List[EditSuggestion]:
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
            ast_node = kwargs.get('ast_node')
            
            # If a specific AST node is provided, only check that node
            if ast_node is not None:
                return self._evaluate_node(ast_node, content)
            
            # Otherwise, check all relevant nodes in the module
            suggestions = []
            
            # Check module-level docstring
            if self.config.require_docstrings and not self._has_docstring(module):
                suggestions.append(self._create_missing_docstring_suggestion(module, content))
            
            # Check all functions and classes
            for node in ast.walk(module):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    if not self._should_skip_node(node, content):
                        suggestions.extend(self._evaluate_node(node, content))
            
            return suggestions
            
        except (SyntaxError, ValueError) as e:
            # If we can't parse the content, return an empty list of suggestions
            return []
    
    def _evaluate_node(self, node: ast.AST, content: str) -> List[EditSuggestion]:
        """Evaluate a single AST node for documentation issues."""
        suggestions = []
        
        # Check for missing docstrings
        if self.config.require_docstrings and not self._has_docstring(node):
            suggestions.append(self._create_missing_docstring_suggestion(node, content))
        
        # Check existing docstring quality
        docstring = ast.get_docstring(node, clean=False)
        if docstring:
            suggestions.extend(self._check_docstring_quality(node, docstring, content))
        
        # Check type hints
        if self.config.require_type_hints and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            suggestions.extend(self._check_type_hints(node, content))
        
        return suggestions
    
    def _should_skip_node(self, node: ast.AST, content: str) -> bool:
        """Determine if a node should be skipped based on ignore patterns."""
        if not hasattr(node, 'name') or not node.name:
            return False
            
        # Skip private methods (except __init__)
        if node.name.startswith('_') and node.name != '__init__':
            return True
            
        # Skip test methods
        if node.name.startswith('test_'):
            return True
            
        # Check against ignore patterns
        node_text = ast.get_source_segment(content, node) or ''
        for pattern in self._compiled_ignore_patterns:
            if pattern.search(node_text) or pattern.search(node.name):
                return True
                
        return False
    
    def _has_docstring(self, node: ast.AST) -> bool:
        """Check if a node has a docstring."""
        if not hasattr(node, 'body') or not node.body:
            return False
            
        first = node.body[0]
        return (isinstance(first, ast.Expr) and 
                isinstance(first.value, ast.Constant) and 
                isinstance(first.value.value, str))
    
    def _create_missing_docstring_suggestion(self, node: ast.AST, content: str) -> EditSuggestion:
        """Create a suggestion for a missing docstring."""
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return self._create_missing_function_docstring(node, content)
        elif isinstance(node, ast.ClassDef):
            return self._create_missing_class_docstring(node, content)
        else:  # Module
            return self._create_missing_module_docstring(node, content)
    
    def _create_missing_function_docstring(self, node: ast.FunctionDef, content: str) -> EditSuggestion:
        """Create a suggestion for a missing function docstring."""
        # Generate a docstring based on the function signature
        docstring = self._generate_function_docstring(node)
        
        # Find where to insert the docstring
        lines = content.splitlines()
        start_line = node.lineno - 1  # Convert to 0-based
        
        # Find the end of the function signature
        insert_line = start_line + 1
        while insert_line < len(lines) and not lines[insert_line].strip().startswith(':'):
            insert_line += 1
        
        if insert_line < len(lines):
            insert_line += 1  # Move past the colon line
        
        # Get indentation
        indent = self._get_indent(lines[start_line])
        
        # Format the docstring with proper indentation
        docstring_lines = [f'{indent}"""{docstring}']
        docstring_lines.append(f'{indent}"""')
        docstring_text = '\n'.join(docstring_lines)
        
        return EditSuggestion(
            operation=EditOperation.ADD,
            criteria=[EditCriteria.DOCUMENTATION, EditCriteria.COMPLETENESS],
            original_text='',
            suggested_text=docstring_text,
            explanation=f"Missing docstring for function '{node.name}'",
            line_number=insert_line + 1,  # Convert back to 1-based
            metadata={"node_type": "function", "node_name": node.name}
        )
    
    def _create_missing_class_docstring(self, node: ast.ClassDef, content: str) -> EditSuggestion:
        """Create a suggestion for a missing class docstring."""
        docstring = f"{node.name} class."
        
        lines = content.splitlines()
        start_line = node.lineno - 1  # Convert to 0-based
        
        # Find where to insert the docstring (after the class definition)
        insert_line = start_line + 1
        while insert_line < len(lines) and not lines[insert_line].strip().startswith(':'):
            insert_line += 1
        
        if insert_line < len(lines):
            insert_line += 1  # Move past the colon line
        
        # Get indentation
        indent = self._get_indent(lines[start_line])
        
        # Format the docstring with proper indentation
        docstring_lines = [f'{indent}"""{docstring}']
        docstring_lines.append(f'{indent}"""')
        docstring_text = '\n'.join(docstring_lines)
        
        return EditSuggestion(
            operation=EditOperation.ADD,
            criteria=[EditCriteria.DOCUMENTATION, EditCriteria.COMPLETENESS],
            original_text='',
            suggested_text=docstring_text,
            explanation=f"Missing docstring for class '{node.name}'",
            line_number=insert_line + 1,  # Convert back to 1-based
            metadata={"node_type": "class", "node_name": node.name}
        )
    
    def _create_missing_module_docstring(self, node: ast.Module, content: str) -> EditSuggestion:
        """Create a suggestion for a missing module docstring."""
        docstring = "Module docstring."
        
        lines = content.splitlines()
        insert_line = 0
        
        # Skip shebang and encoding
        if lines and (lines[0].startswith('#!') or lines[0].startswith('# -*-')):
            insert_line = 1
        
        # Skip any other comments at the top
        while insert_line < len(lines) and lines[insert_line].strip().startswith('#'):
            insert_line += 1
        
        # If there's a docstring right after, don't add another one
        if (insert_line < len(lines) and 
            (lines[insert_line].strip().startswith('"""') or 
             lines[insert_line].strip().startswith("'" * 3) or
             lines[insert_line].strip().startswith("r\"\"\"") or
             lines[insert_line].strip().startswith("r'''"))):
            return None
        
        # Get indentation
        indent = ''
        if insert_line < len(lines):
            indent_match = re.match(r'^\s*', lines[insert_line])
            if indent_match:
                indent = indent_match.group(0)
        
        # Format the docstring
        docstring_lines = [f'{indent}"""{docstring}']
        docstring_lines.append(f'{indent}"""')
        docstring_text = '\n'.join(docstring_lines)
        
        return EditSuggestion(
            operation=EditOperation.ADD,
            criteria=[EditCriteria.DOCUMENTATION, EditCriteria.COMPLETENESS],
            original_text='',
            suggested_text=docstring_text,
            explanation="Missing module docstring",
            line_number=insert_line + 1,  # Convert to 1-based
            metadata={"node_type": "module"}
        )
    
    def _check_docstring_quality(self, node: ast.AST, docstring: str, content: str) -> List[EditSuggestion]:
        """Check the quality of an existing docstring."""
        suggestions = []
        
        try:
            # Parse the docstring
            parsed = parse_docstring(docstring, self.config.docstring_style)
            
            # Check for empty docstring
            if not parsed.summary.strip():
                suggestions.append(EditSuggestion(
                    operation=EditOperation.REWRITE,
                    criteria=[EditCriteria.DOCUMENTATION, EditCriteria.QUALITY],
                    original_text=docstring,
                    suggested_text='""\n    Docstring here.\n    """',
                    explanation="Empty docstring",
                    line_number=node.lineno + 1 if hasattr(node, 'lineno') else 1,
                    metadata={"node_type": type(node).__name__.lower()}
                ))
            
            # Check sections based on node type
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                suggestions.extend(self._check_function_docstring(node, parsed, content))
            elif isinstance(node, ast.ClassDef):
                suggestions.extend(self._check_class_docstring(node, parsed, content))
            
            # Check line length in docstring
            for i, line in enumerate(docstring.split('\n')):
                if len(line) > self.config.max_line_length:
                    suggestions.append(EditSuggestion(
                        operation=EditOperation.REWRITE,
                        criteria=[EditCriteria.DOCUMENTATION, EditCriteria.STYLE],
                        original_text=line,
                        suggested_text=line[:self.config.max_line_length],
                        explanation=f"Docstring line too long ({len(line)} > {self.config.max_line_length} characters)",
                        line_number=(node.lineno + i + 1) if hasattr(node, 'lineno') else (i + 1),
                        metadata={"node_type": type(node).__name__.lower()}
                    ))
            
        except Exception as e:
            # If we can't parse the docstring, suggest a complete rewrite
            suggestions.append(EditSuggestion(
                operation=EditOperation.REWRITE,
                criteria=[EditCriteria.DOCUMENTATION, EditCriteria.QUALITY],
                original_text=docstring,
                suggested_text='""\n    Docstring here.\n    """',
                explanation=f"Invalid docstring format: {str(e)}",
                line_number=node.lineno + 1 if hasattr(node, 'lineno') else 1,
                metadata={"node_type": type(node).__name__.lower()}
            ))
        
        return suggestions
    
    def _check_function_docstring(self, 
                                node: Union[ast.FunctionDef, ast.AsyncFunctionDef], 
                                parsed: ParsedDocstring,
                                content: str) -> List[EditSuggestion]:
        """Check the quality of a function docstring."""
        suggestions = []
        
        # Check for parameters section
        if self.config.require_args_section and 'Args' not in parsed.sections:
            # Get function parameters
            args = [arg.arg for arg in node.args.args if arg.arg != 'self']
            
            if args or node.args.vararg or node.args.kwarg:
                suggestions.append(self._create_missing_section_suggestion(
                    node, 
                    'Args', 
                    self._generate_args_section(node),
                    "Missing 'Args' section in function docstring"
                ))
        
        # Check for returns section if the function has a return statement
        if self.config.require_returns_section and 'Returns' not in parsed.sections:
            # Check if the function has a return statement that returns a value
            has_return_value = any(
                isinstance(n, ast.Return) and n.value is not None
                for n in ast.walk(node)
            )
            
            if has_return_value or node.returns:
                suggestions.append(self._create_missing_section_suggestion(
                    node,
                    'Returns',
                    '    Description of return value',
                    "Missing 'Returns' section in function docstring"
                ))
        
        # Check for examples section if required
        if self.config.require_examples_section and 'Examples' not in parsed.sections:
            suggestions.append(self._create_missing_section_suggestion(
                node,
                'Examples',
                '    >>> result = function_name()',
                "Missing 'Examples' section in function docstring"
            ))
        
        return suggestions
    
    def _check_class_docstring(self, node: ast.ClassDef, parsed: ParsedDocstring, content: str) -> List[EditSuggestion]:
        """Check the quality of a class docstring."""
        suggestions = []
        
        # Check for attributes section if the class has attributes
        if 'Attributes' not in parsed.sections:
            # Look for class attributes and instance attributes
            has_attributes = any(
                isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
                for n in ast.walk(node)
            )
            
            if has_attributes:
                suggestions.append(self._create_missing_section_suggestion(
                    node,
                    'Attributes',
                    '    attribute_name: Description of attribute',
                    "Missing 'Attributes' section in class docstring"
                ))
        
        # Check for methods section if the class has methods
        if 'Methods' not in parsed.sections:
            has_methods = any(
                isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                for n in node.body
            )
            
            if has_methods:
                suggestions.append(self._create_missing_section_suggestion(
                    node,
                    'Methods',
                    '    method_name(): Description of method',
                    "Missing 'Methods' section in class docstring"
                ))
        
        return suggestions
    
    def _create_missing_section_suggestion(self, 
                                         node: ast.AST, 
                                         section_name: str, 
                                         section_content: str,
                                         explanation: str) -> EditSuggestion:
        """Create a suggestion for a missing docstring section."""
        # Get the existing docstring
        docstring = ast.get_docstring(node, clean=False)
        if not docstring:
            return None
            
        # Create the new docstring with the missing section
        parsed = parse_docstring(docstring, self.config.docstring_style)
        
        # Add the missing section
        parsed.sections[section_name] = section_content
        
        # Convert back to string
        new_docstring = parsed.to_string()
        
        # Format with triple quotes
        lines = ['"""' + new_docstring]
        lines.append('"""')
        new_docstring = '\n'.join(lines)
        
        # Get the indentation
        node_text = ast.get_source_segment(self._get_source(node), node)
        indent = self._get_indent(node_text)
        
        # Apply indentation
        new_docstring = '\n'.join(
            indent + line if line.strip() else ''
            for line in new_docstring.split('\n')
        )
        
        return EditSuggestion(
            operation=EditOperation.REWRITE,
            criteria=[EditCriteria.DOCUMENTATION, EditCriteria.COMPLETENESS],
            original_text=docstring,
            suggested_text=new_docstring,
            explanation=explanation,
            line_number=node.lineno + 1 if hasattr(node, 'lineno') else 1,
            metadata={"node_type": type(node).__name__.lower(), "section": section_name}
        )
    
    def _check_type_hints(self, node: Union[ast.FunctionDef, ast.AsyncFunctionDef], content: str) -> List[EditSuggestion]:
        """Check for missing type hints in function parameters and return type."""
        suggestions = []
        
        # Check return type annotation
        if self.config.check_missing_return_type and node.returns is None:
            suggestions.append(self._create_missing_type_hint_suggestion(
                node, 
                "return", 
                f"Return type hint is missing for function '{node.name}'"
            ))
        
        # Check parameter type annotations
        if self.config.check_missing_param_types:
            for arg in node.args.args:
                if arg.arg != 'self' and arg.annotation is None:
                    suggestions.append(self._create_missing_type_hint_suggestion(
                        node, 
                        f"parameter '{arg.arg}'", 
                        f"Type hint for parameter '{arg.arg}' is missing in function '{node.name}'"
                    ))
        
        return suggestions
    
    def _create_missing_type_hint_suggestion(self, 
                                            node: ast.AST, 
                                            location: str, 
                                            message: str) -> EditSuggestion:
        """Create a suggestion for a missing type hint."""
        return EditSuggestion(
            operation=EditOperation.ADD,
            criteria=[EditCriteria.DOCUMENTATION, EditCriteria.CLARITY],
            original_text='',
            suggested_text='',  # This would be filled in by the apply method
            explanation=message,
            line_number=node.lineno if hasattr(node, 'lineno') else 1,
            metadata={"type_hint_location": location, "node_type": type(node).__name__.lower()}
        )
    
    def _generate_function_docstring(self, node: Union[ast.FunctionDef, ast.AsyncFunctionDef]) -> str:
        """Generate a docstring for a function."""
        docstring = [f"{node.name}."]
        
        # Add a blank line after the summary
        docstring.append("")
        
        # Add Args section if there are parameters
        args = [arg for arg in node.args.args if arg.arg != 'self']
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
        
        return '\n'.join(docstring)
    
    def _generate_args_section(self, node: Union[ast.FunctionDef, ast.AsyncFunctionDef]) -> str:
        """Generate the Args section for a function docstring."""
        args = [arg for arg in node.args.args if arg.arg != 'self']
        if not args and not node.args.vararg and not node.args.kwarg:
            return ""
            
        lines = ["    Args:"]
        
        # Add regular arguments
        for arg in args:
            arg_type = f" ({ast.unparse(arg.annotation)})" if arg.annotation else ""
            lines.append(f"        {arg.arg}{arg_type}: Description of {arg.arg}")
        
        # Add varargs
        if node.args.vararg:
            lines.append(f"        *{node.args.vararg.arg}: Variable length argument list")
        
        # Add kwargs
        if node.args.kwarg:
            lines.append(f"        **{node.args.kwarg.arg}: Arbitrary keyword arguments")
        
        return '\n'.join(lines)
    
    def _get_indent(self, line: str) -> str:
        """Get the indentation of a line."""
        match = re.match(r'^\s*', line)
        return match.group(0) if match else ''
    
    def _get_source(self, node: ast.AST) -> str:
        """Get the source code for a node."""
        # This is a simplified version - in a real implementation, you'd want to
        # get the source from the original file or a source map
        return ast.unparse(node)

    def get_config(self) -> Dict[str, Any]:
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
            "ignore_patterns": self.config.ignore_patterns
        }
