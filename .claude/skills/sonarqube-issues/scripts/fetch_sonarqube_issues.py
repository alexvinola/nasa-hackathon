#!/usr/bin/env python3
"""Read SonarQube Server issues using environment variables or the project's .env."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

MAX_ATTEMPTS = 3
MAX_RETRY_DELAY = 30
MAX_RESPONSE_BYTES = 5 * 1024 * 1024
RETRY_STATUSES = {429, 500, 502, 503, 504}
SEVERITIES = ("BLOCKER", "CRITICAL", "HIGH", "MAJOR", "MEDIUM", "MINOR", "LOW", "INFO")


class FetchError(RuntimeError):
    """A safe diagnostic with no credentials or remote response body."""


def load_settings(project_dir):
    """Read only Sonar settings; never execute .env or override process variables."""
    keys = ("SONAR_HOST_URL", "SONAR_TOKEN")
    settings = {key: os.environ[key] for key in keys if key in os.environ}
    if len(settings) < len(keys):
        try:
            lines = (Path(project_dir) / ".env").read_text(encoding="utf-8-sig").splitlines()
        except FileNotFoundError:
            lines = []
        except (OSError, UnicodeError):
            raise FetchError("Cannot read the project's .env; check its permissions and UTF-8.") \
                from None
        for number, raw in enumerate(lines, 1):
            line = raw.strip()
            if line.startswith("export "):
                line = line[7:].lstrip()
            key, separator, value = line.partition("=")
            key = key.strip()
            if key not in keys or key in os.environ:
                continue
            value = value.strip()
            if not separator:
                raise FetchError(f"Invalid {key} assignment on .env line {number}.")
            if value.startswith(("'", '"')):
                end = value.find(value[0], 1)
                tail = value[end + 1:].strip() if end >= 0 else "invalid"
                if end < 0 or (tail and not tail.startswith("#")):
                    raise FetchError(f"Invalid {key} quoting on .env line {number}.")
                value = value[1:end]
            else:
                value = re.split(r"\s+#", value, maxsplit=1)[0].rstrip()
            settings[key] = value
    missing = [key for key in keys if not settings.get(key, "").strip()]
    if missing:
        raise FetchError(
            f"Missing configuration: {', '.join(missing)}. Set them in the project's .env "
            "(current directory, or --project-dir), or in the process environment. "
            "Use SONAR_HOST_URL=https://your-sonarqube and SONAR_TOKEN=<your-token>. "
            "Keep .env Git-ignored and enter the token locally, never in chat."
        )
    return settings


def server_url(value):
    value = value.strip()
    try:
        parts = urlsplit(value)
        valid = (parts.scheme == "https" and parts.hostname and not parts.username
                 and not parts.password and not parts.query and not parts.fragment)
        parts.port  # Reject malformed ports before constructing a request.
    except ValueError:
        valid = False
    if not valid or any(char.isspace() or ord(char) < 32 for char in value):
        raise FetchError("SONAR_HOST_URL must be an HTTPS URL without credentials/query/fragment.")
    return value.rstrip("/")


def origin(url):
    parts = urlsplit(url)
    return parts.scheme, parts.hostname, parts.port or 443


class SameOriginRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        try:
            destination = urlsplit(newurl)
            allowed = (destination.scheme == "https" and not destination.username
                       and not destination.password and origin(req.full_url) == origin(newurl)
                       and not any(c.isspace() or ord(c) < 32 for c in newurl))
        except ValueError:
            allowed = False
        if not allowed:
            raise FetchError("Refused an unsafe SonarQube redirect; check SONAR_HOST_URL.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def retry_delay(header, attempt):
    delay = 2 ** attempt
    if header:
        try:
            delay = max(0, int(header))
        except ValueError:
            try:
                date = parsedate_to_datetime(header)
                delay = max(0, (date - datetime.now(timezone.utc)).total_seconds())
            except (ValueError, TypeError, OverflowError):
                pass
    if delay > MAX_RETRY_DELAY:
        raise FetchError("Server requested a longer retry delay; retry this command later.")
    return delay


class Client:
    def __init__(self, url, token):
        self.url = server_url(url)
        if not token or not token.isascii() or any(c.isspace() or ord(c) < 32 for c in token):
            raise FetchError("SONAR_TOKEN must be nonempty ASCII without whitespace or controls.")
        self.authorization = f"Bearer {token}"
        self.opener = build_opener(SameOriginRedirect())

    def get(self, path, query):
        request = Request(
            f"{self.url}/{path}?{urlencode(query)}",
            headers={"Accept": "application/json", "Authorization": self.authorization},
            method="GET",
        )
        for attempt in range(MAX_ATTEMPTS):
            try:
                with self.opener.open(request, timeout=30) as response:
                    payload = response.read(MAX_RESPONSE_BYTES + 1)
                if len(payload) > MAX_RESPONSE_BYTES:
                    raise FetchError("SonarQube response exceeded the size limit.")
                try:
                    return json.loads(payload)
                except (ValueError, UnicodeError):
                    raise FetchError("SonarQube returned invalid JSON.") from None
            except HTTPError as error:
                status = error.code
                retry_after = error.headers.get("Retry-After") if error.headers else None
                error.close()
                if status in RETRY_STATUSES and attempt + 1 < MAX_ATTEMPTS:
                    time.sleep(retry_delay(retry_after, attempt))
                    continue
                raise FetchError(
                    f"SonarQube HTTP {status}; check access, project/scope and server availability."
                ) from None
            except (URLError, OSError, ValueError):
                raise FetchError("Unable to read SonarQube; check network/TLS and configuration.") \
                    from None
        raise AssertionError("Retry loop must return or raise")


def validate_project(client, project):
    result = client.get("api/components/show", {"component": project})
    component = result.get("component") if isinstance(result, dict) else None
    if (not isinstance(component, dict) or component.get("key") != project
            or component.get("qualifier") != "TRK"):
        raise FetchError("Server did not return the exact requested project.")


def validate_page(data, page, size):
    if not isinstance(data, dict) or not isinstance(data.get("issues"), list):
        raise FetchError("Invalid issue response: missing issues list.")
    paging = data.get("paging")
    if paging is None:
        paging = {"pageIndex": data.get("p"), "pageSize": data.get("ps"),
                  "total": data.get("total")}
    if not isinstance(paging, dict):
        raise FetchError("Invalid paging metadata.")
    index, actual_size, total = (paging.get(k) for k in ("pageIndex", "pageSize", "total"))
    if (any(type(v) is not int for v in (index, actual_size, total))
            or index != page or actual_size != size or total < 0):
        raise FetchError("Invalid or unexpected paging metadata.")
    issues = data["issues"]
    if len(issues) != max(0, min(size, total - (page - 1) * size)):
        raise FetchError("Incomplete issue page; cannot establish coverage.")
    for issue in issues:
        if (not isinstance(issue, dict)
                or any(not isinstance(issue.get(k), str) or not issue[k]
                       for k in ("key", "component", "rule"))
                or not isinstance(issue.get("message"), str)):
            raise FetchError("Invalid issue identity or message.")
        impacts = issue.get("impacts", [])
        if not isinstance(impacts, list) or any(
            not isinstance(impact, dict)
            or any(not isinstance(impact.get(k), str) or not impact[k]
                   for k in ("softwareQuality", "severity")) for impact in impacts
        ):
            raise FetchError("Invalid issue impacts.")
        if any(k in issue and not isinstance(issue[k], str) for k in ("severity", "type")):
            raise FetchError("Invalid legacy issue classification.")
    components = data.get("components", [])
    if not isinstance(components, list) or any(
        not isinstance(c, dict) or not isinstance(c.get("key"), str)
        or ("path" in c and not isinstance(c["path"], str)) for c in components
    ):
        raise FetchError("Invalid components list.")
    return issues, components, total


def collect(client, project, branch=None, pull_request=None, page_size=100, max_pages=5):
    validate_project(client, project)
    query = {"componentKeys": project, "resolved": "false", "ps": page_size}
    if branch:
        query["branch"] = branch
    if pull_request:
        query["pullRequest"] = pull_request
    issues, seen, components = [], set(), {}
    total = None
    for page in range(1, max_pages + 1):
        data = client.get("api/issues/search", dict(query, p=page))
        batch, page_components, page_total = validate_page(data, page, page_size)
        if total is not None and total != page_total:
            raise FetchError("Issue total changed while paging; rerun for a consistent result.")
        total = page_total
        for issue in batch:
            if issue["key"] in seen:
                raise FetchError("Duplicate issue across pages; cannot establish coverage.")
            seen.add(issue["key"])
            issues.append(issue)
        components.update({c["key"]: c for c in page_components})
        if len(issues) == total:
            break
    scope = {"branch": branch} if branch else (
        {"pull_request": pull_request} if pull_request else {"branch": "main (server default)"}
    )
    return {"project": project, "scope": scope, "total": total, "returned": len(issues),
            "complete": len(issues) == total, "pages_fetched": page,
            "issues": issues, "components": list(components.values())}


def clean(value):
    return " ".join("".join(c for c in str(value) if c.isprintable() or c.isspace()).split())


def severity(issue):
    impacts = issue.get("impacts", [])
    values = [i["severity"] for i in impacts] or [issue.get("severity", "UNKNOWN")]
    return min(values, key=lambda v: SEVERITIES.index(v) if v in SEVERITIES else len(SEVERITIES))


def render_triage(report):
    counts = Counter(severity(issue) for issue in report["issues"])
    ordered = sorted(counts, key=lambda s: SEVERITIES.index(s) if s in SEVERITIES else 99)
    lines = [f"Project: {report['project']}; scope: {report['scope']}",
             f"Unresolved issues: {report['total']} total; fetched {report['returned']}.",
             "Coverage: " + ("complete" if report["complete"] else "PARTIAL (page limit reached)"),
             "Displayed severity: " + (", ".join(f"{s}: {counts[s]}" for s in ordered) or "none")]
    paths = {c["key"]: c.get("path", c["key"]) for c in report["components"]}
    for issue in sorted(report["issues"], key=lambda i: ordered.index(severity(i))):
        impacts = issue.get("impacts", [])
        category = ", ".join(f"{i['softwareQuality']}:{i['severity']}" for i in impacts)
        category = category or f"{issue.get('type', 'UNKNOWN')}:{severity(issue)}"
        path = paths.get(issue["component"], issue["component"])
        path = path.removeprefix(report["project"] + ":")
        text_range = issue.get("textRange") or {}
        line = issue.get("line") or (
            text_range.get("startLine", "?") if isinstance(text_range, dict) else "?"
        )
        message = clean(issue["message"])
        if len(message) > 600:
            message = message[:600] + "... [truncated; use --format json]"
        lines.append(f"- {clean(issue['key'])} [{clean(category)}] {clean(issue['rule'])} | "
                     f"{clean(path)}:{clean(line)} | {message}")
    return "\n".join(lines)


def parse_arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", help="Exact SonarQube project key")
    parser.add_argument("--project-dir", type=Path, default=Path.cwd(),
                        help="Directory containing .env (default: current directory)")
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--branch")
    scope.add_argument("--pull-request")
    parser.add_argument("--format", choices=("triage", "json"), default="triage")
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--max-pages", type=int, default=5)
    args = parser.parse_args(argv)
    for value in (args.project, args.branch, args.pull_request):
        if value is not None and (not value.strip() or value != value.strip()
                                  or any(ord(c) < 32 for c in value)):
            parser.error("Project and scope must be nonempty, without surrounding whitespace.")
    if "," in args.project:
        parser.error("Specify exactly one project key.")
    if not 1 <= args.page_size <= 500 or not 1 <= args.max_pages <= 20:
        parser.error("--page-size must be 1..500 and --max-pages must be 1..20.")
    return args


def main(argv=None):
    args = parse_arguments(argv)
    try:
        settings = load_settings(args.project_dir)
        client = Client(settings["SONAR_HOST_URL"], settings["SONAR_TOKEN"])
        report = collect(client, args.project, args.branch, args.pull_request,
                         args.page_size, args.max_pages)
        print(json.dumps(report, ensure_ascii=False, indent=2) if args.format == "json"
              else render_triage(report))
        return 0 if report["complete"] else 2
    except FetchError as error:
        print(f"SonarQube retrieval failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
