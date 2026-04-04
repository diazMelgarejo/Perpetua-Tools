```markdown
# Perplexity-Tools Development Patterns

> Auto-generated skill from repository analysis

## Overview
This skill teaches you the core development patterns and conventions used in the Perplexity-Tools Python codebase. You'll learn about file organization, import/export styles, commit message standards, and how to write and run tests. This guide is designed to help you contribute effectively and maintain consistency across the project.

## Coding Conventions

### File Naming
- Use **snake_case** for all file names.
  - Example: `data_parser.py`, `utils_helper.py`

### Import Style
- Use **relative imports** within the package.
  - Example:
    ```python
    from .utils import parse_data
    ```

### Export Style
- Use **named exports** by explicitly listing exported functions/classes in `__all__`.
  - Example:
    ```python
    __all__ = ['parse_data', 'DataLoader']
    ```

### Commit Messages
- Follow **conventional commit** patterns.
- Use prefixes like `docs` for documentation changes.
- Keep commit messages concise (average ~69 characters).
  - Example:
    ```
    docs: update README with installation instructions
    ```

## Workflows

### Documentation Updates
**Trigger:** When updating or adding documentation  
**Command:** `/update-docs`

1. Make your documentation changes in the relevant `.md` or docstring files.
2. Stage your changes:
    ```
    git add <file>
    ```
3. Commit using the `docs` prefix:
    ```
    git commit -m "docs: <brief description of doc update>"
    ```
4. Push your changes:
    ```
    git push
    ```

### Adding New Python Modules
**Trigger:** When creating a new feature or utility module  
**Command:** `/add-module`

1. Create a new Python file using snake_case naming (e.g., `my_feature.py`).
2. Use relative imports to access other modules.
    ```python
    from .utils import helper_function
    ```
3. Define your functions/classes and add them to `__all__` if you want them exported.
    ```python
    __all__ = ['my_function']
    ```
4. Write or update tests as needed (see Testing Patterns).
5. Commit your changes with an appropriate conventional commit message.
6. Push your changes.

## Testing Patterns

- Test files follow the pattern `*.test.*` (e.g., `utils.test.py`).
- The testing framework is **unknown**; check existing test files for conventions.
- Place tests alongside or near the modules they test.
- Example test file name: `data_parser.test.py`
- To run tests, use the standard Python test runner or the project's preferred tool (check project docs or ask a maintainer).

## Commands
| Command        | Purpose                                  |
|----------------|------------------------------------------|
| /update-docs   | Update or add project documentation      |
| /add-module    | Add a new Python module to the codebase  |
```
