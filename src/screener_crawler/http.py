from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Self
from urllib.parse import urljoin, urlsplit

import httpx
from tenacity import (
    Retrying,
    before_sleep_log,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


logger = logging.getLogger(__name__)


class RetryableHttpStatusError(RuntimeError):
    """Raised for retryable HTTP status codes."""

    def __init__(self, response: httpx.Response):
        self.response = response
        super().__init__(f"Retryable HTTP status {response.status_code} for {response.request.url}")


class RobotsDisallowedError(PermissionError):
    """Raised when robots.txt blocks a requested URL."""


@dataclass(slots=True, frozen=True)
class RobotsRule:
    pattern: str
    allow: bool
    regex: re.Pattern[str]
    specificity: int

    @classmethod
    def from_pattern(cls, pattern: str, allow: bool) -> Self | None:
        cleaned = pattern.strip()
        if not cleaned:
            return None

        anchored = cleaned.endswith("$")
        body = cleaned[:-1] if anchored else cleaned
        escaped = re.escape(body).replace(r"\*", ".*")
        regex = re.compile("^" + escaped + ("$" if anchored else ""))
        specificity = len(body.replace("*", ""))
        return cls(pattern=cleaned, allow=allow, regex=regex, specificity=specificity)

    def matches(self, target: str) -> bool:
        return bool(self.regex.match(target))


@dataclass(slots=True, frozen=True)
class RobotsGroup:
    user_agents: tuple[str, ...]
    rules: tuple[RobotsRule, ...]


class RobotsPolicy:
    def __init__(self, groups: list[RobotsGroup], user_agent: str):
        self._groups = groups
        self.user_agent = user_agent.lower()

    @classmethod
    def from_text(cls, text: str, user_agent: str) -> Self:
        groups: list[RobotsGroup] = []
        current_agents: list[str] = []
        current_rules: list[RobotsRule] = []

        def flush_group() -> None:
            nonlocal current_agents, current_rules
            if current_agents:
                groups.append(
                    RobotsGroup(
                        user_agents=tuple(current_agents),
                        rules=tuple(current_rules),
                    )
                )
            current_agents = []
            current_rules = []

        for raw_line in text.splitlines():
            line = raw_line.split("#", 1)[0].strip()
            if not line:
                continue

            if ":" not in line:
                continue

            field, value = [part.strip() for part in line.split(":", 1)]
            field_lower = field.lower()
            value_lower = value.lower()

            if field_lower == "user-agent":
                if current_rules:
                    flush_group()
                current_agents.append(value_lower)
                continue

            if field_lower not in {"allow", "disallow"}:
                continue

            if not current_agents:
                continue

            rule = RobotsRule.from_pattern(value, allow=field_lower == "allow")
            if rule is not None:
                current_rules.append(rule)

        flush_group()
        return cls(groups=groups, user_agent=user_agent)

    def can_fetch(self, url: str) -> bool:
        applicable_rules = self._matching_rules()
        target = self._target_from_url(url)

        best_rule: RobotsRule | None = None
        for rule in applicable_rules:
            if not rule.matches(target):
                continue
            if best_rule is None or rule.specificity > best_rule.specificity:
                best_rule = rule
                continue
            if best_rule is not None and rule.specificity == best_rule.specificity and rule.allow:
                best_rule = rule

        if best_rule is None:
            return True
        return best_rule.allow

    def _matching_rules(self) -> tuple[RobotsRule, ...]:
        matched_groups: list[RobotsGroup] = []
        best_specificity = -1

        for group in self._groups:
            matching_agents = [
                agent
                for agent in group.user_agents
                if agent == "*" or agent in self.user_agent
            ]
            if not matching_agents:
                continue

            group_specificity = max(len(agent.replace("*", "")) for agent in matching_agents)
            if group_specificity > best_specificity:
                matched_groups = [group]
                best_specificity = group_specificity
            elif group_specificity == best_specificity:
                matched_groups.append(group)

        rules: list[RobotsRule] = []
        for group in matched_groups:
            rules.extend(group.rules)
        return tuple(rules)

    @staticmethod
    def _target_from_url(url: str) -> str:
        parts = urlsplit(url)
        target = parts.path or "/"
        if parts.query:
            target = f"{target}?{parts.query}"
        return target


class ScreenerHttpClient:
    def __init__(
        self,
        *,
        user_agent: str,
        timeout_seconds: float,
        delay_seconds: float,
        max_retries: int,
    ) -> None:
        self.user_agent = user_agent
        self.delay_seconds = delay_seconds
        self.max_retries = max_retries
        self._last_request_at = 0.0
        self._retryer = Retrying(
            retry=retry_if_exception_type((httpx.HTTPError, RetryableHttpStatusError)),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            stop=stop_after_attempt(max_retries),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        )
        self._client = httpx.Client(
            timeout=timeout_seconds,
            follow_redirects=True,
            headers={
                "User-Agent": user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.8",
            },
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def fetch(self, url: str) -> httpx.Response:
        return self._retryer(self._fetch_once, url)

    def _fetch_once(self, url: str) -> httpx.Response:
        self._sleep_if_needed()
        logger.info("Fetching %s", url)
        response = self._client.get(url)
        self._last_request_at = time.monotonic()

        if response.status_code in {429, 500, 502, 503, 504}:
            raise RetryableHttpStatusError(response)

        response.raise_for_status()
        return response

    def _sleep_if_needed(self) -> None:
        if self.delay_seconds <= 0:
            return

        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.delay_seconds:
            sleep_seconds = self.delay_seconds - elapsed
            logger.debug("Sleeping %.2f seconds before next request", sleep_seconds)
            time.sleep(sleep_seconds)


def load_robots_policy(client: ScreenerHttpClient, site_url: str) -> RobotsPolicy:
    robots_url = urljoin(site_url, "/robots.txt")
    response = client.fetch(robots_url)
    return RobotsPolicy.from_text(response.text, user_agent=client.user_agent)
