#!/usr/bin/env python3
"""
jobradar skills — dictionary of QA Automation technologies and practices.

Why: in a 3–4k-character description the stack is named in two or three words,
and those words decide whether a vacancy is interesting. Highlighted, they read
in seconds; buried in prose, they don't.

This is a dictionary FOR DISPLAY, not the skill taxonomy from Phase 1
(docs/PRODUCT.md §7). That one will be a separate DB table with a structured
extract and proficiency levels; this highlighting stores nothing and affects
nothing — it can be dropped without touching data.

Order within a group is irrelevant: before the pattern is built the terms are
sorted by length anyway, so "REST Assured" wins over "REST".
"""

import html
import re

# Programming languages. .NET/C# live here too: in vacancies they effectively name the language.
LANGUAGES = (
    "TypeScript",
    "JavaScript",
    "Python",
    "Java",
    "C#",
    "C++",
    ".NET",
    "Kotlin",
    "Swift",
    "Ruby",
    "Golang",
    "Go",
    "PHP",
    "Scala",
    "Groovy",
    "Bash",
    "Shell",
    "SQL",
    "PL/SQL",
    "T-SQL",
    "JS",
)

UI_AUTOMATION = (
    "Playwright",
    "Cypress",
    "Selenium",
    "Selenide",
    "WebdriverIO",
    "Puppeteer",
    "TestCafe",
    "Appium",
    "XCUITest",
    "Espresso",
    "Detox",
    "Maestro",
    "WebDriver",
    "Android",
    "iOS",
    "DevTools",
    "Selenium Grid",
    "BrowserStack",
    "Sauce Labs",
    "LambdaTest",
)

FRAMEWORKS = (
    "pytest",
    "unittest",
    "Jest",
    "Vitest",
    "Mocha",
    "Chai",
    "Jasmine",
    "Karma",
    "JUnit",
    "TestNG",
    "NUnit",
    "xUnit",
    "MSTest",
    "Robot Framework",
    "Cucumber",
    "SpecFlow",
    "Behave",
    "Serenity",
    "Allure",
    "ReportPortal",
    "Playwright Test",
    "Faker",
    "AssertJ",
    "Hamcrest",
    "Gherkin",
    "Karate",
)

API = (
    "REST",
    "RESTful",
    "GraphQL",
    "gRPC",
    "SOAP",
    "WebSocket",
    "OpenAPI",
    "Swagger",
    "Postman",
    "Newman",
    "REST Assured",
    "RestSharp",
    "SuperTest",
    "Requests",
    "HTTPX",
    "Pact",
    "WireMock",
    "MockServer",
    "Mountebank",
    "JSON Schema",
    "HTTP",
    "HTTPS",
    "JSON",
    "XML",
    "YAML",
    "TCP/IP",
)

PERFORMANCE = (
    "JMeter",
    "k6",
    "Gatling",
    "Locust",
    "Artillery",
    "BlazeMeter",
    "Lighthouse",
)

CI = (
    "CI/CD",
    "Jenkins",
    "GitHub Actions",
    "GitLab CI",
    "Azure DevOps",
    "TeamCity",
    "CircleCI",
    "Bamboo",
    "Travis CI",
    "ArgoCD",
    "CI",
    "Git",
    "GitHub",
    "GitLab",
    "Bitbucket",
    "Azure Pipelines",
)

INFRA = (
    "Docker",
    "Kubernetes",
    "K8s",
    "Helm",
    "Terraform",
    "Ansible",
    "AWS",
    "Azure",
    "GCP",
    "Linux",
    "Nginx",
    "Grafana",
    "Prometheus",
    "Datadog",
    "Sentry",
    "Kibana",
    "Splunk",
    "ELK",
    "OpenTelemetry",
)

DATA = (
    "PostgreSQL",
    "MySQL",
    "MSSQL",
    "Oracle",
    "MongoDB",
    "Redis",
    "Cassandra",
    "Elasticsearch",
    "OpenSearch",
    "Kafka",
    "RabbitMQ",
    "ActiveMQ",
    "Snowflake",
    "BigQuery",
    "Databricks",
    "Airflow",
    "Spark",
)

# Approaches, practices, kinds of testing. What doesn't get installed from a package.
APPROACHES = (
    "BDD",
    "TDD",
    "ATDD",
    "DDD",
    "shift-left",
    "shift left",
    "test pyramid",
    "піраміда тестування",
    "Page Object",
    "POM",
    "data-driven",
    "keyword-driven",
    "risk-based",
    "exploratory testing",
    "exploratory",
    "regression testing",
    "regression",
    "smoke testing",
    "smoke",
    "sanity",
    "e2e",
    "end-to-end",
    "integration testing",
    "unit testing",
    "component testing",
    "contract testing",
    "acceptance testing",
    "UAT",
    "performance testing",
    "load testing",
    "stress testing",
    "security testing",
    "penetration testing",
    "chaos engineering",
    "mutation testing",
    "visual testing",
    "visual regression",
    "accessibility",
    "a11y",
    "WCAG",
    "localization testing",
    "i18n",
    "cross-browser",
    "test design",
    "тест-дизайн",
    "test strategy",
    "test plan",
    "test case",
    "тест-кейс",
    "code review",
    "pair programming",
    "mocking",
    "stubbing",
    "service virtualization",
    "flaky tests",
    "quality gates",
    "definition of done",
    "Agile",
    "Scrum",
    "Kanban",
    "SAFe",
    "DevOps",
    "SDET",
    "QA Automation",
    "SDLC",
    "STLC",
    "ISTQB",
    "AQA",
    "manual testing",
    "мануальне тестування",
    "UI/API",
    "UI",
    "API",
)

# AI/ML — separate, since it's the fastest-growing slice of QA and it's right in
# the profile (LLM/ML output validation on the IDP project).
AI = (
    "AI",
    "LLM",
    "GenAI",
    "AI-assisted",
    "MCP",
    "prompt engineering",
    "prompt",
    "RAG",
    "embeddings",
    "vector database",
    "hallucination",
    "ground truth",
    "model validation",
    "evaluation",
    "eval",
    "benchmark",
    "fine-tuning",
    "Machine Learning",
    "ML",
    "NLP",
    "OCR",
    "IDP",
    "computer vision",
    "Copilot",
    "OpenAI",
    "Anthropic",
    "Claude",
    "ChatGPT",
    "LangChain",
)

MANAGEMENT = (
    "Jira",
    "Confluence",
    "TestRail",
    "Zephyr",
    "X-Ray",
    "Qase",
    "TestLink",
    "Azure Test Plans",
    "Notion",
)

# Frontend. Only what isn't already in other groups: TypeScript/JavaScript
# live in "мови", GraphQL in "API", WCAG/a11y in "підходи".
FRONTEND = (
    "React",
    "Vue",
    "Angular",
    "Svelte",
    "Next.js",
    "Nuxt",
    "Redux",
    "MobX",
    "Zustand",
    "RxJS",
    "Webpack",
    "Vite",
    "Rollup",
    "Babel",
    "ESLint",
    "Prettier",
    "Sass",
    "SCSS",
    "LESS",
    "Tailwind",
    "Bootstrap",
    "HTML",
    "CSS",
    "jQuery",
    "Storybook",
    "Astro",
    "SolidJS",
    "Web Components",
    "Styled Components",
    "Figma",
    "PWA",
    "SSR",
)

# Backend. gRPC/REST/GraphQL in "API", databases in "дані", .NET in "мови".
BACKEND = (
    "Node.js",
    "Express",
    "NestJS",
    "Fastify",
    "Django",
    "Flask",
    "FastAPI",
    "Spring",
    "Spring Boot",
    "Hibernate",
    "Rails",
    "Laravel",
    "Symfony",
    "ASP.NET",
    "Gin",
    "Celery",
    "SQLAlchemy",
    "Prisma",
    "TypeORM",
    "Sequelize",
    "microservices",
    "message queue",
    "OAuth",
    "JWT",
    "WebSockets",
)

GROUPS = {
    "мови": LANGUAGES,
    "UI-автоматизація": UI_AUTOMATION,
    "фреймворки": FRAMEWORKS,
    "API": API,
    "продуктивність": PERFORMANCE,
    "CI/CD": CI,
    "інфраструктура": INFRA,
    "дані": DATA,
    "підходи": APPROACHES,
    "AI/ML": AI,
    "керування": MANAGEMENT,
    "фронтенд": FRONTEND,
    "бекенд": BACKEND,
}

# English display labels for the internal group keys. The keys stay Ukrainian
# because roles.py and candidate.py reference them as identifiers; only what the
# UI shows is translated here.
GROUP_LABELS = {
    "мови": "Languages",
    "UI-автоматизація": "UI automation",
    "фреймворки": "Frameworks",
    "API": "API",
    "продуктивність": "Performance",
    "CI/CD": "CI/CD",
    "інфраструктура": "Infrastructure",
    "дані": "Data",
    "підходи": "Approaches",
    "AI/ML": "AI/ML",
    "керування": "Management",
    "фронтенд": "Frontend",
    "бекенд": "Backend",
}


def group_label(name):
    """UI label for an internal group key; the key itself if it has none."""
    return GROUP_LABELS.get(name, name)


ALL_TERMS = tuple(sorted({t for group in GROUPS.values() for t in group}))

# Canonical spelling from the dictionary — so "PYTEST" from one vacancy and
# "pytest" from another are the same tag, not two.
CANONICAL = {t.lower(): t for t in ALL_TERMS}
GROUP_OF = {t.lower(): name for name, group in GROUPS.items() for t in group}


# Terms that collide with ordinary English words. Found on live data: "safe
# failure behaviour" became the SAFe tag, and "post go-live" the Go tag. For
# these, spelling matters; the rest stay case-insensitive, since E2E/Pytest/
# JIRA/Typescript are all legitimate variants.
CASE_SENSITIVE = ("Go", "SAFe")


def _build_pattern():
    """One regex for all terms.

    Longer terms go first, otherwise "REST" would eat "REST Assured" and "Java"
    would eat "JavaScript". Word boundaries are done by hand: \\b doesn't work
    with terms that start or end in #, + or a dot (C#, C++, .NET). Case-
    insensitivity is enabled locally — (?i:…) on the group, not a flag on the
    whole regex — so Go and SAFe stay case-sensitive.
    """
    loose = sorted(
        (t for t in ALL_TERMS if t not in CASE_SENSITIVE), key=len, reverse=True
    )
    strict = sorted(CASE_SENSITIVE, key=len, reverse=True)
    body = "(?i:{})".format("|".join(re.escape(term) for term in loose))
    if strict:
        body += "|" + "|".join(re.escape(term) for term in strict)
    return re.compile(rf"(?<![\w#+])(?:{body})(?![\w#+])")


PATTERN = _build_pattern()

# Split HTML into tags and text: only text may be highlighted, otherwise "API"
# inside an href or a class name would turn into broken markup.
TAG_SPLIT = re.compile(r"(<[^>]*>)")


def highlight_html(markup, href_builder=None):
    """Wrap the terms it finds, leaving markup untouched.

    Without href_builder a term just becomes bold; with it, a link to a search
    on that tag. One function, so highlighting and search never diverge on what
    counts as a term.
    """
    if not markup:
        return markup

    def wrap(match):
        word = match.group(0)
        if href_builder is None:
            return f'<b class="tech">{word}</b>'
        # Escape right here: a urlencoded href contains "&", and without this the
        # markup is technically broken, and a "&copy" in a param would become a symbol.
        return f'<a class="tech" href="{html.escape(href_builder(canonical(word)), quote=True)}">{word}</a>'

    out = []
    for chunk in TAG_SPLIT.split(markup):
        out.append(chunk if chunk.startswith("<") else PATTERN.sub(wrap, chunk))
    return "".join(out)


def canonical(term):
    """Dictionary spelling of a term (pytest, not PYTEST)."""
    return CANONICAL.get(str(term).lower(), str(term))


def found_terms(text):
    """Which terms are mentioned, in the text's spelling, without duplicates."""
    seen = []
    for match in PATTERN.finditer(text or ""):
        term = match.group(0)
        if term.lower() not in {s.lower() for s in seen}:
            seen.append(term)
    return seen


# Group order for the card. First what answers "what is this vacancy about"
# (language, automation tool, framework), and approaches last: "Agile" and
# "regression" are almost everywhere and distinguish nothing.
CARD_PRIORITY = (
    "мови",
    "UI-автоматизація",
    "фреймворки",
    "AI/ML",
    "API",
    "продуктивність",
    "дані",
    "інфраструктура",
    "CI/CD",
    "керування",
    "підходи",
)


def card_terms(text, limit=10):
    """Tags for the card: (visible, hidden).

    Showing everything found is impossible — a typical description has close to
    two dozen, and the card turns into clutter. So we sort by group, and within
    a group keep order of appearance in the text: a vacancy title names the
    stack first, and not by accident. Hidden ones aren't dropped — the card
    itself expands them.
    """
    order = {name: i for i, name in enumerate(CARD_PRIORITY)}
    found = [canonical(t) for t in found_terms(text)]
    ranked = sorted(
        enumerate(found),
        key=lambda pair: (order.get(GROUP_OF.get(pair[1].lower(), ""), 99), pair[0]),
    )
    terms = [term for _, term in ranked]
    return terms[:limit], terms[limit:]


def mentions(text, term):
    """Whether this exact term is mentioned — with the same word boundaries as the highlight.

    Needed separately from LIKE '%term%': a substring search for "Java" would
    find every vacancy with "JavaScript", which is exactly the mistake the
    dictionary was built to avoid.
    """
    word = CANONICAL.get(str(term).lower())
    if not word:
        return False
    flags = 0 if word in CASE_SENSITIVE else re.IGNORECASE
    pattern = re.compile(rf"(?<![\w#+]){re.escape(word)}(?![\w#+])", flags)
    return bool(pattern.search(text or ""))


def tally(texts):
    """How many VACANCIES mention each term.

    We count vacancies, not mentions: a description where "Playwright" appears
    eight times is one vacancy with Playwright, not eight.
    """
    counts = {}
    for text in texts:
        for term in {t.lower() for t in found_terms(text)}:
            counts[canonical(term)] = counts.get(canonical(term), 0) + 1
    return counts
