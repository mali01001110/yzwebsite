# CLAUDE.md - System & Coding Guidelines for Claude Code

This file defines the engineering standards, architecture rules, security protocols, and coding conventions that Claude Code must strictly follow when working on this repository.

---

## 1. General Coding Guidelines

* **Naming Conventions:**
  * Use `camelCase` for variable names, function parameters, and class property names.
  * Use `PascalCase` for class names, interfaces, type definitions, and components.
  * Use `UPPER_SNAKE_CASE` for global constants and environment variables.
* **Function Granularity:**
  * Keep functions small, modular, and focused on a single responsibility.
  * Limit function length; split complex tasks into helper functions.
* **Self-Documenting Code:**
  * Choose clear, descriptive, and unambiguous names for variables, functions, and classes.
  * Avoid redundant or obvious comments (e.g., `// increment i by 1`). Comments should explain *why*, not *what*.
* **Readability Over Cleverness:**
  * Prefer clear, explicit logic over dense, nested, or obscure "clever" one-liners.

---

## 2. Clean Code Principles

* **DRY (Don't Repeat Yourself):**
  * Abstract repeated logic into reusable functions, helper modules, or utilities.
  * Avoid duplicate constants, schemas, or query strings across the codebase.
* **KISS (Keep It Simple, Stupid):**
  * Strive for simplicity in software design.
  * Avoid over-engineering, unnecessary abstractions, or overly complex class hierarchies.
* **YAGNI (You Aren't Gonna Need It):**
  * Implement only the functionality currently required.
  * Do not build speculative features, premature abstractions, or unused code paths.
* **Consistent Formatting & Linting:**
  * Adhere strictly to configured linter and formatter settings (e.g., ESLint, Prettier, Black, Ruff, Flake8).
  * Maintain consistent indentation, line wrapping, spacing, and quote styles across all files.

---

## 3. Application Security

* **Input Validation & Sanitization:**
  * Always validate and sanitize all external user inputs at the boundary (APIs, parameters, payloads, headers).
  * Enforce strict type checking, length constraints, and allowed-character whitelists.
* **Database & Query Security:**
  * ALWAYS use parameterized queries or trusted ORM/query builders to prevent SQL Injection.
  * Never concatenate strings to build raw database queries.
* **Secrets Management:**
  * NEVER hardcode credentials, API keys, JWT secrets, passwords, or private tokens in source code.
  * Store all sensitive credentials in environment variables (`.env`) or dedicated secret managers (e.g., Vault, AWS Secrets Manager). Ensure `.env` files are gitignored.
* **Principle of Least Privilege:**
  * Restrict database users, API keys, and service roles to the exact permissions required for their task.
* **Error Handling & Information Disclosure:**
  * Implement robust, centralized error handling.
  * Log detailed stack traces internally, but return sanitized, generic error responses to external clients to avoid leaking system details or stack traces.

---

## 4. Object-Oriented Programming (OOP) & Design Standards

* **SOLID Principles:**
  * **S - Single Responsibility Principle:** Every class or module should have one, and only one, reason to change.
  * **O - Open/Closed Principle:** Software entities should be open for extension, but closed for modification.
  * **L - Liskov Substitution Principle:** Derived classes must be completely substitutable for their base classes without breaking behavior.
  * **I - Interface Segregation Principle:** Prefer smaller, client-specific interfaces over large, monolithic ones.
  * **D - Dependency Inversion Principle:** Depend on abstractions (interfaces/abstract classes), not on concrete implementations.
* **Composition Over Inheritance:**
  * Favor object composition and delegation over class inheritance hierarchies to achieve flexible, reusable designs.
* **Encapsulation:**
  * Hide internal object state behind private/protected fields; expose explicit methods or getters/setters to interact with state safely.
* **Design Patterns:**
  * Apply recognized design patterns judiciously where appropriate:
    * **Factory Pattern:** For encapsulating complex object creation logic.
    * **Strategy Pattern:** For interchanging algorithms or execution behaviors dynamically.
    * **Observer Pattern:** For event-driven architectures and decoupled messaging.

---

## 5. Testing & Quality Assurance

* **Unit Testing:**
  * Write isolated, reliable unit tests for all critical business logic and complex calculations.
  * Mock external dependencies (network, databases, file system) in unit tests.
* **Integration Testing:**
  * Use integration tests to verify API endpoints, database interactions, and inter-service workflows.
* **Test Quality & Coverage:**
  * Target high code coverage, but prioritize writing meaningful, scenario-driven tests over vanity metrics.
  * Test both success paths ("happy paths") and edge/error conditions.
* **Automated Security & Code Quality Checks:**
  * Integrate automated linting, type checking, static analysis, and dependency vulnerability scanning (e.g., Snyk, Dependabot, SonarQube) into the CI/CD pipeline.

---

## 6. Documentation & Collaboration

* **Documentation Maintenance:**
  * Keep the root `README.md` updated with setup instructions, prerequisites, running commands, and environment setup.
  * Maintain precise, up-to-date API documentation (e.g., OpenAPI / Swagger specs).
* **Git Commit Conventions:**
  * Use clear, imperative, and structured commit messages (e.g., Conventional Commits: `feat: add user authentication`, `fix: resolve SQL injection risk`, `refactor: extract helper function`).
* **Architectural Decision Records (ADRs):**
  * Document major architecture and technology decisions in ADR files (`docs/adr/000X-title.md`).
* **Code Reviews:**
  * Conduct thorough code reviews focused on readability, maintainability, performance, adherence to guidelines, and application security.
