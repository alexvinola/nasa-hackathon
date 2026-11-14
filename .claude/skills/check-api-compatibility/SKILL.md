---
name: check-api-compatibility
description: Compare baseline and candidate OpenAPI contracts for changes that break existing clients. Use for API compatibility checks in Java, .NET, Python or other HTTP APIs, not for a general code review.
---

# Check API compatibility

## Establish the comparison

- Identify the API/document/version and compatibility policy. Baseline is the
  contract currently supported by consumers, or the user-specified revision;
  candidate is the proposed contract. State both origins and revisions/hashes.
  For a PR, use its actual target/base when that is the intended reference.
- Use checked-in contracts, release artifacts or the project's existing generation
  command. Generate both sides consistently for the same document/group/profile.
  A stale baseline or a different audience/version can invalidate the comparison.
- This checks HTTP wire contracts. It does not check Java/.NET binary compatibility,
  event schemas or behavior absent from OpenAPI. If no faithful contract exists,
  explain the gap; do not manufacture one and declare the API compatible.

## Obtain the contracts

Follow the actual stack and configured paths:

| Stack | Existing contract sources to look for |
|---|---|
| Java/Spring Boot | Committed specs, springdoc generation/plugin, configured API-docs endpoint (often `/v3/api-docs`) |
| ASP.NET Core | Committed specs, Swashbuckle/NSwag or built-in OpenAPI generation; configured document/build artifact or `/openapi/{documentName}.json` |
| Python/FastAPI | Committed/generated specs or the configured OpenAPI endpoint (often `/openapi.json`) |
| Other HTTP APIs | Their existing OpenAPI generator or published specification |

Prefer existing artifacts; use disposable local/test environments when generation
needs an application. ASP.NET build-time generation can execute startup code, and
Spring generation can start a service: use the project's safe generation profile.
Do not change dependencies or expose documentation in production to obtain specs.
Preserve local `$ref` files and relative paths. Resolve external references only
from the intended sources; an unresolved reference is a failed check.

## Compare with oasdiff

Use the local `oasdiff` CLI with local contracts. Check its installed version and
`oasdiff breaking --help`; use existing project configuration and record severity
overrides/exclusions because they affect the result. If unavailable, guide local
setup (`brew install oasdiff` on macOS/Linux, or the official binary on Windows).
Installation is developer setup, not an implicit part of every compatibility check.

```bash
oasdiff breaking base.yaml candidate.yaml --format json --fail-on ERR
oasdiff changelog base.yaml candidate.yaml --format json
```

Paths are examples: use the project's actual documents. Keep the order baseline
then candidate. `--fail-on ERR` makes breaking findings fail the command; a tool,
parse or reference error also means the check did not pass. Inspect diagnostics
and output rather than interpreting every nonzero exit as a compatibility finding.
Do not upload private contracts to an online diff/review service by default.

## Interpret and report

1. Group findings by operation (`METHOD /path`) and schema/property. Prioritize
   removed operations, newly required request fields, restricted accepted values,
   response changes, authentication and serialization contracts.
2. Check request and response directions separately: accepting fewer inputs and
   returning values outside the old contract have different consumer effects.
   Check enums, nullability, formats, status codes, headers and content types.
   Avoid blanket rules such as "adding a field is always safe".
3. Inspect the changed handler/DTO/serializer and relevant consumer/contract tests.
   OpenAPI can omit defaults, validation, authorization behavior, error semantics
   or side effects; flag material behavior changes separately from spec findings.
4. Report baseline/candidate provenance, tool version/configuration, affected
   operations, finding IDs/locations, consumer impact and an actionable remedy
   (preserve the contract, migrate clients, or introduce an API version).
5. Do not silently refresh the baseline, suppress findings or rewrite contracts
   to match the candidate. For requested fixes, change source and regenerate specs,
   then rerun the comparison and relevant tests. A clean diff means no detected
   contract break within the checked scope, not proof of identical runtime behavior.

References:
- https://www.oasdiff.com/docs/getting-started
- https://www.oasdiff.com/docs/breaking-changes
- https://springdoc.org/
- https://learn.microsoft.com/en-us/aspnet/core/fundamentals/openapi/aspnetcore-openapi
