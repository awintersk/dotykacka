# Contribution Guidelines

Thank you for your interest in contributing to our project! To ensure a smooth contribution process, please follow these
guidelines.

# Contribution Guidelines

Thank you for your interest in contributing to our project! To ensure a smooth contribution process, please follow these guidelines.

## Reporting Issues

- Make sure you've actually read the error message if there is one, it may really help
- No need to create an issue if you're making a PR to fix it. Describe the issue in the PR, it's the same as an issue, but with higher priority!
- Double-check that the issue still occurs with the latest version of Odoo (you can easily test this on Runbot)
- Search for similar issues before reporting anything
- If you're not sure it's a bug, search in Odoo Help or ask a question there to find out
- If you're a programmer, try investigating/fixing yourself, and consider making a Pull Request instead
- If you really think a new issue is useful, keep in mind that it will be treated with a much lower priority than a Pull Request or an Odoo Enterprise support ticket

## Branch Naming Convention

When creating a new branch for your changes, please follow the naming pattern:

* main-branch-task-identifier-description-initials

Replace the placeholders with the appropriate information:

- `main-branch-dev`: The name of the main branch in the repository (e.g., `13.0`, `16.0`).
- `task-identifier`: A unique identifier for the task or issue you're working on (e.g., ticket number, issue number).
- `description`: A short description of the changes you're making.
- `initials`: Your initials or username.

Example: `13.0-dev-3249116-receipt_tax_hungary_rounding-faremir`

## Submitting a Pull Request

1. Make sure your fork is up to date with the main repository before creating a pull request.
2. Create a new pull request by going to the main repository's "Pull Requests" tab and clicking on "New Pull Request." Choose the main repository and main branch as the "base repository" and "base branch," respectively. Choose your forked repository and the new branch you created as the "head repository" and "compare branch," respectively.
3. Give your pull request a clear and descriptive title. In the description, provide any necessary context or details about the changes you've made.
4. Ensure that your pull request adheres to any project-specific requirements, such as passing tests, code style, or documentation.
5. Wait for the project maintainers to review your pull request. They may request changes or ask for clarification. Please address any feedback promptly to ensure a smooth merging process.

## Creating Issues

- Before creating a new issue, search the existing issues to make sure a similar issue hasn't already been reported. If you find an existing issue that matches your report, feel free to add any additional information or subscribe to the issue to receive updates.
- Give your issue a clear and descriptive title that summarizes the problem or feature request. This helps maintainers and other contributors quickly understand the purpose of your issue.
- In the issue description, provide as much relevant information as possible. For bug reports, include steps to reproduce the issue, any error messages, and information about your environment (e.g., operating system, browser, software version). For feature requests, describe the desired functionality and explain why it would be useful.
- If applicable, use labels and milestones to categorize your issue. This helps maintainers prioritize and organize issues. However, if you're unsure about which labels or milestones to use, leave them blank and let the
