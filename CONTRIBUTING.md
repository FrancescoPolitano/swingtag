# Contributing

Bug reports, questions and pull requests are welcome.

## Issues

Open an issue for a bug or a proposal. For a bug, include what you did, what you expected and
what happened, the Terraform and Python versions, and the anomaly lines from the publisher's
log group if a page was not published. Never paste AWS account numbers, credentials or private
URLs.

## Pull requests

1. Fork the repository and create a branch from `main`.
2. Set up the environment and run the checks:

   ```sh
   make venv && make test                       # unit tests
   terraform fmt -check -recursive
   terraform -chdir=terraform test              # module tests with mocked AWS
   node terraform/functions/test_rewrite.mjs    # CloudFront function
   ```

3. Add or update tests for every change in behaviour.
4. Keep the pull request focused on one change and describe why it is needed.

CI runs the same checks on every pull request.

## Conventions

- English in code, comments and documentation; pages are localised (`en`, `it`).
- Imports inside the package are relative; the project name appears under `src/` only in
  `__init__.py`, and Terraform derives every resource name from `var.name` (both are tested).
- Example media are small static files committed as they are, each under 100 KB.
- Example item folders always carry a valid token (`Label · abcdefghijkm`).

By contributing you agree that your contribution is licensed under the MIT License.
