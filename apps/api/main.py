import os
import json
import time
from html.parser import HTMLParser
from typing import Any
from urllib.parse import quote, urljoin, urlparse
from urllib.request import Request, urlopen

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from sqlalchemy import create_engine, text

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL) if DATABASE_URL else None

app = FastAPI(title="PerfMind AI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    url: HttpUrl


class GithubAnalyzeRequest(BaseModel):
    repo_url: HttpUrl


class PerfHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.images: list[dict[str, str]] = []
        self.scripts: list[dict[str, str]] = []
        self.stylesheets: list[dict[str, str]] = []
        self.preloads: list[dict[str, str]] = []
        self.inline_styles = 0
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key.lower(): value or "" for key, value in attrs}
        tag = tag.lower()

        if tag == "title":
            self._in_title = True
        elif tag == "img":
            self.images.append(attr)
        elif tag == "script":
            self.scripts.append(attr)
        elif tag == "link":
            rel = attr.get("rel", "").lower()
            if "stylesheet" in rel:
                self.stylesheets.append(attr)
            if "preload" in rel or "modulepreload" in rel:
                self.preloads.append(attr)
        elif tag == "style":
            self.inline_styles += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data.strip()


def tone_for(value: float, good: float, warn: float, reverse: bool = False) -> str:
    if reverse:
        if value >= good:
            return "good"
        if value >= warn:
            return "warn"
        return "bad"

    if value <= good:
        return "good"
    if value <= warn:
        return "warn"
    return "bad"


def issue(title: str, impact: str, evidence: str, fix: str) -> dict[str, str]:
    return {
        "title": title,
        "impact": impact,
        "evidence": evidence,
        "fix": fix,
    }


def suggestion(title: str, priority: str, evidence: str, recommendation: str) -> dict[str, str]:
    return {
        "title": title,
        "priority": priority,
        "evidence": evidence,
        "recommendation": recommendation,
    }


def infer_site_profile(url: str, html: str) -> dict[str, Any]:
    lower = html.lower()
    signals = {
        "ecommerce": [
            "cart",
            "checkout",
            "add to cart",
            "buy now",
            "product",
            "price",
            "₹",
            "$",
            "order",
            "wishlist",
            "payment",
        ],
        "saas": ["pricing", "dashboard", "sign in", "sign up", "workspace", "subscription", "trial", "api key"],
        "content": ["blog", "article", "author", "category", "newsletter", "read more"],
        "portfolio": ["portfolio", "projects", "resume", "skills", "contact me", "case study"],
        "education": ["course", "lesson", "quiz", "student", "learn", "certificate", "assignment"],
    }
    counts = {kind: sum(1 for token in tokens if token in lower) for kind, tokens in signals.items()}
    site_type = max(counts, key=counts.get)
    confidence = min(0.95, 0.35 + counts[site_type] * 0.1)

    if counts[site_type] == 0:
        site_type = "general"
        confidence = 0.35

    needs_database = site_type in {"ecommerce", "saas", "education"} or any(
        token in lower
        for token in ["login", "account", "checkout", "cart", "orders", "booking", "admin", "user profile", "payment"]
    )

    reasons = []
    if "cart" in lower or "checkout" in lower:
        reasons.append("cart or checkout flow")
    if "login" in lower or "sign in" in lower or "account" in lower:
        reasons.append("user accounts")
    if "product" in lower or "price" in lower or "₹" in lower or "$" in lower:
        reasons.append("products or pricing")
    if "course" in lower or "student" in lower:
        reasons.append("student/course data")

    return {
        "type": site_type,
        "confidence": round(confidence, 2),
        "needs_database": needs_database,
        "database_reason": ", ".join(reasons) if reasons else "static content signals only",
        "signals": counts,
    }


def build_business_suggestions(url: str, html: str, summary: dict[str, int]) -> list[dict[str, str]]:
    profile = infer_site_profile(url, html)
    suggestions: list[dict[str, str]] = []

    if profile["needs_database"]:
        suggestions.append(
            suggestion(
                "Add a real backend/database model",
                "High",
                f"PerfMind classified this as {profile['type']} with signals for {profile['database_reason']}.",
                "Use a database for users, products, orders, sessions, analytics, and admin workflows instead of hardcoded frontend data.",
            )
        )

    if profile["type"] == "ecommerce":
        suggestions.extend(
            [
                suggestion(
                    "Prioritize product and checkout performance",
                    "High",
                    "The page contains commerce signals such as cart, checkout, product, price, or order text.",
                    "Keep product images optimized, cache product lists, prefetch checkout-critical routes, and monitor conversion-impacting Web Vitals.",
                ),
                suggestion(
                    "Track business-critical frontend errors",
                    "High",
                    "E-commerce sites lose revenue when add-to-cart, payment, or checkout scripts fail.",
                    "Capture JS errors and failed API requests with route, browser, device, and release metadata.",
                ),
            ]
        )
    elif profile["type"] == "saas":
        suggestions.append(
            suggestion(
                "Separate marketing and app bundles",
                "Medium",
                "The site has SaaS signals such as pricing, dashboard, workspace, subscription, or sign-in text.",
                "Keep the landing page lightweight and lazy-load authenticated dashboard code after login.",
            )
        )
    elif profile["type"] == "education":
        suggestions.append(
            suggestion(
                "Persist learning progress and user activity",
                "High",
                "Education signals such as course, lesson, student, quiz, or certificate were detected.",
                "Use a database for users, enrollments, progress, assignments, certificates, and personalized recommendations.",
            )
        )
    elif profile["type"] == "portfolio":
        suggestions.append(
            suggestion(
                "Keep the site static and image-focused",
                "Medium",
                "Portfolio signals were detected, so the site may not need a full database.",
                "Use static generation, optimized project images, contact form protection, and lightweight analytics.",
            )
        )

    if summary.get("image_count", 0) > 8:
        suggestions.append(
            suggestion(
                "Build an image optimization pipeline",
                "Medium",
                f"The scan found {summary['image_count']} image references.",
                "Compress images, serve AVIF/WebP, define responsive sizes, and lazy-load non-critical visuals.",
            )
        )

    if summary.get("script_count", 0) > 10:
        suggestions.append(
            suggestion(
                "Reduce JavaScript shipped on first load",
                "Medium",
                f"The scan found {summary['script_count']} script references.",
                "Split code by route, defer third-party scripts, and dynamically import heavy interactive widgets.",
            )
        )

    if not suggestions:
        suggestions.append(
            suggestion(
                "Add continuous monitoring before scaling",
                "Medium",
                "The page does not strongly match a complex dynamic app, but regressions can still happen after changes.",
                "Add Web Vitals collection, release tracking, and Lighthouse CI so performance changes are caught before users complain.",
            )
        )

    return suggestions[:6]


def metric_from_audit(
    label: str,
    audit: dict[str, Any] | None,
    unit: str,
    good: float,
    warn: float,
    divisor: float = 1,
) -> dict[str, str]:
    numeric_value = audit.get("numericValue") if audit else None
    if numeric_value is None:
        return {"label": label, "value": "n/a", "unit": "", "tone": "neutral"}

    value = float(numeric_value) / divisor
    formatted = f"{value:.2f}" if unit == "s" else str(int(round(value)))
    return {
        "label": label,
        "value": formatted,
        "unit": unit,
        "tone": tone_for(value, good, warn),
    }


def lighthouse_issue(
    audits: dict[str, Any],
    audit_id: str,
    title: str,
    impact: str,
    fix: str,
) -> dict[str, str] | None:
    audit = audits.get(audit_id)
    if not audit:
        return None

    score = audit.get("score")
    numeric_value = audit.get("numericValue")
    details = audit.get("displayValue") or audit.get("description") or "Lighthouse flagged this audit."

    if score is not None and score >= 0.9:
        return None

    if numeric_value is not None and numeric_value <= 0:
        return None

    return issue(title, impact, str(details), fix)


def run_pagespeed_analysis(url: str) -> dict[str, Any] | None:
    api_url = (
        "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
        f"?url={quote(url, safe='')}&strategy=mobile&category=performance"
    )
    request = Request(
        api_url,
        headers={
            "User-Agent": "PerfMindAI/1.0 (+frontend-performance-monitoring-agent)",
            "Accept": "application/json",
        },
    )

    try:
        started = time.perf_counter()
        with urlopen(request, timeout=45) as response:
            payload = json.loads(response.read().decode("utf-8", errors="ignore"))
        elapsed_ms = int((time.perf_counter() - started) * 1000)
    except Exception:
        return None

    lighthouse = payload.get("lighthouseResult", {})
    audits = lighthouse.get("audits", {})
    categories = lighthouse.get("categories", {})
    performance_score = categories.get("performance", {}).get("score")
    score = int(round(float(performance_score or 0) * 100))

    cls_audit = audits.get("cumulative-layout-shift")
    cls_value = cls_audit.get("numericValue") if cls_audit else None
    cls_display = "n/a" if cls_value is None else f"{float(cls_value):.3f}"

    metrics = [
        {
            "label": "Performance Score",
            "value": str(score),
            "unit": "/100",
            "tone": tone_for(score, 90, 70, reverse=True),
        },
        metric_from_audit("LCP", audits.get("largest-contentful-paint"), "s", 2.5, 4.0, divisor=1000),
        {
            "label": "CLS",
            "value": cls_display,
            "unit": "",
            "tone": "neutral" if cls_value is None else tone_for(float(cls_value), 0.1, 0.25),
        },
        metric_from_audit("FCP", audits.get("first-contentful-paint"), "s", 1.8, 3.0, divisor=1000),
        metric_from_audit("TBT", audits.get("total-blocking-time"), "ms", 200, 600),
        metric_from_audit("TTFB", audits.get("server-response-time"), "ms", 800, 1800),
    ]

    possible_issues = [
        lighthouse_issue(
            audits,
            "largest-contentful-paint",
            "Largest Contentful Paint needs attention",
            "High",
            "Optimize the LCP element, preload the critical asset, compress above-the-fold media, and reduce render-blocking work.",
        ),
        lighthouse_issue(
            audits,
            "cumulative-layout-shift",
            "Layout shift detected",
            "High",
            "Reserve space for images, ads, banners, embeds, and late-loading components using dimensions or aspect-ratio.",
        ),
        lighthouse_issue(
            audits,
            "render-blocking-resources",
            "Render-blocking resources found",
            "Medium",
            "Inline critical CSS, defer non-critical CSS/JS, and remove blocking third-party scripts from the initial path.",
        ),
        lighthouse_issue(
            audits,
            "unused-javascript",
            "Unused JavaScript is increasing page weight",
            "Medium",
            "Split bundles by route, dynamically import heavy widgets, and remove unused dependencies.",
        ),
        lighthouse_issue(
            audits,
            "uses-optimized-images",
            "Images can be optimized",
            "Medium",
            "Serve compressed AVIF/WebP images and avoid oversized source files.",
        ),
        lighthouse_issue(
            audits,
            "modern-image-formats",
            "Images are not using modern formats",
            "Medium",
            "Convert large JPEG/PNG assets to AVIF or WebP and use responsive image sources.",
        ),
        lighthouse_issue(
            audits,
            "offscreen-images",
            "Offscreen images are loading too early",
            "Medium",
            "Lazy-load below-the-fold images and prioritize only the visual content needed for first paint.",
        ),
        lighthouse_issue(
            audits,
            "total-byte-weight",
            "Page transfer size is high",
            "Medium",
            "Compress assets, remove unused code, enable caching, and split non-critical resources.",
        ),
        lighthouse_issue(
            audits,
            "third-party-summary",
            "Third-party code affects performance",
            "Medium",
            "Audit analytics, tag managers, widgets, and ads. Load them after the primary experience is interactive.",
        ),
        lighthouse_issue(
            audits,
            "server-response-time",
            "Server response time is slow",
            "Medium",
            "Add CDN caching, reduce backend/database latency, and prerender static pages where possible.",
        ),
    ]
    issues = [item for item in possible_issues if item is not None]

    if not issues:
        issues.append(
            issue(
                "No major Lighthouse performance issue found",
                "Low",
                "PageSpeed Insights did not flag a major mobile performance opportunity in the selected audits.",
                "Keep monitoring Web Vitals in production because real users can still reveal device, browser, and region-specific regressions.",
            )
        )

    network_requests = audits.get("network-requests", {}).get("details", {}).get("items", [])
    total_byte_weight = audits.get("total-byte-weight", {}).get("numericValue") or 0
    final_url = lighthouse.get("finalUrl") or url
    title = audits.get("document-title", {}).get("displayValue") or urlparse(final_url).hostname or final_url

    return {
        "scanner": "pagespeed-lighthouse",
        "url": final_url,
        "title": title,
        "status_code": 200,
        "summary": {
            "html_bytes": int(total_byte_weight),
            "image_count": len([item for item in network_requests if str(item.get("resourceType", "")).lower() == "image"]),
            "script_count": len([item for item in network_requests if str(item.get("resourceType", "")).lower() == "script"]),
            "stylesheet_count": len([item for item in network_requests if str(item.get("resourceType", "")).lower() == "stylesheet"]),
            "blocking_script_count": len(audits.get("render-blocking-resources", {}).get("details", {}).get("items", [])),
            "missing_image_dimension_count": len(audits.get("image-aspect-ratio", {}).get("details", {}).get("items", [])),
            "external_script_count": len([item for item in network_requests if str(item.get("resourceType", "")).lower() == "script" and urlparse(item.get("url", "")).hostname != urlparse(final_url).hostname]),
        },
        "metrics": metrics,
        "issues": issues[:8],
        "recommendations": [
            "Use this Lighthouse scan as the first pass, then connect GitHub to map issues to exact files.",
            "Run scans for both mobile and desktop before release.",
            "Install the PerfMind Web SDK later to compare lab Lighthouse data with real user Web Vitals.",
        ],
        "confidence": 0.9,
        "analysis_note": f"This report uses real Google PageSpeed Insights Lighthouse mobile lab data. API round trip took {elapsed_ms}ms.",
    }


def analyze_html(url: str, html: str, ttfb_ms: int, load_ms: int, status_code: int) -> dict[str, Any]:
    parser = PerfHTMLParser()
    parser.feed(html)

    parsed_url = urlparse(url)
    image_count = len(parser.images)
    script_count = len(parser.scripts)
    blocking_scripts = [
        script
        for script in parser.scripts
        if script.get("src") and "async" not in script and "defer" not in script and script.get("type") != "module"
    ]
    missing_image_dimensions = [
        image
        for image in parser.images
        if image.get("src") and (not image.get("width") or not image.get("height"))
    ]
    lazy_images = [image for image in parser.images if image.get("loading") == "lazy"]
    external_scripts = [
        script
        for script in parser.scripts
        if script.get("src") and urlparse(urljoin(url, script.get("src", ""))).hostname != parsed_url.hostname
    ]

    html_bytes = len(html.encode("utf-8", errors="ignore"))
    lcp_seconds = round(max(0.8, (ttfb_ms / 1000) + 0.8 + min(image_count, 20) * 0.07 + len(blocking_scripts) * 0.18), 2)
    cls = round(min(0.35, len(missing_image_dimensions) * 0.025 + max(0, image_count - len(lazy_images) - 3) * 0.006), 3)
    inp_ms = int(120 + min(script_count, 30) * 9 + len(external_scripts) * 7)

    score = 100
    score -= max(0, int((lcp_seconds - 2.5) * 13))
    score -= max(0, int((cls - 0.1) * 140))
    score -= max(0, int((inp_ms - 200) / 8))
    score -= max(0, int((ttfb_ms - 400) / 25))
    score -= min(18, len(blocking_scripts) * 3)
    score -= min(12, int(max(0, html_bytes - 250_000) / 40_000))
    score = max(20, min(100, score))

    issues: list[dict[str, str]] = []
    if lcp_seconds > 2.5:
        issues.append(
            issue(
                "Likely LCP delay on the initial page",
                "High" if lcp_seconds >= 4 else "Medium",
                f"The page has {image_count} images, {len(blocking_scripts)} blocking scripts, and estimated LCP is {lcp_seconds}s.",
                "Compress and resize above-the-fold images, preload the true hero asset, and defer non-critical scripts.",
            )
        )

    if missing_image_dimensions:
        issues.append(
            issue(
                "Images can cause layout shift",
                "High" if len(missing_image_dimensions) >= 4 else "Medium",
                f"{len(missing_image_dimensions)} image tags are missing width or height attributes.",
                "Add explicit width and height or CSS aspect-ratio for images, banners, logos, and cards.",
            )
        )

    if blocking_scripts:
        issues.append(
            issue(
                "Render-blocking scripts detected",
                "Medium",
                f"{len(blocking_scripts)} script tags load without async, defer, or module behavior.",
                "Add defer/async where safe, move analytics after interaction, and dynamically import heavy widgets.",
            )
        )

    if len(parser.stylesheets) > 6:
        issues.append(
            issue(
                "Many stylesheets on first load",
                "Medium",
                f"The document references {len(parser.stylesheets)} stylesheet files.",
                "Merge critical CSS, remove unused styles, and load route-specific CSS only where needed.",
            )
        )

    if ttfb_ms > 600:
        issues.append(
            issue(
                "Slow server response",
                "High" if ttfb_ms > 1000 else "Medium",
                f"Measured TTFB is around {ttfb_ms}ms from the backend fetch.",
                "Add caching, review server/database latency, and serve static pages through a CDN when possible.",
            )
        )

    if not issues:
        issues.append(
            issue(
                "No major static HTML performance risk found",
                "Low",
                "The initial HTML has reasonable script, image, stylesheet, and layout-shift signals.",
                "Run continuous monitoring with Web Vitals in real browsers to catch device-specific regressions.",
            )
        )

    summary = {
        "html_bytes": html_bytes,
        "image_count": image_count,
        "script_count": script_count,
        "stylesheet_count": len(parser.stylesheets),
        "blocking_script_count": len(blocking_scripts),
        "missing_image_dimension_count": len(missing_image_dimensions),
        "external_script_count": len(external_scripts),
    }

    return {
        "scanner": "static-html",
        "url": url,
        "title": parser.title or parsed_url.hostname or url,
        "status_code": status_code,
        "site_profile": infer_site_profile(url, html),
        "business_suggestions": build_business_suggestions(url, html, summary),
        "summary": summary,
        "metrics": [
            {"label": "Performance Score", "value": str(score), "unit": "/100", "tone": tone_for(score, 90, 70, reverse=True)},
            {"label": "LCP", "value": str(lcp_seconds), "unit": "s", "tone": tone_for(lcp_seconds, 2.5, 4.0)},
            {"label": "CLS", "value": str(cls), "unit": "", "tone": tone_for(cls, 0.1, 0.25)},
            {"label": "INP", "value": str(inp_ms), "unit": "ms", "tone": tone_for(inp_ms, 200, 500)},
            {"label": "TTFB", "value": str(ttfb_ms), "unit": "ms", "tone": tone_for(ttfb_ms, 400, 800)},
            {"label": "Resources", "value": str(image_count + script_count + len(parser.stylesheets)), "unit": "", "tone": tone_for(image_count + script_count + len(parser.stylesheets), 45, 85)},
        ],
        "issues": issues,
        "recommendations": [
            "Connect the GitHub repository to map these symptoms to exact components and files.",
            "Run this scan on both mobile and desktop URLs or deployments before release.",
            "Install the PerfMind Web SDK later to capture true field Web Vitals from users.",
        ],
        "confidence": 0.76,
        "analysis_note": "This report uses a real URL fetch and local static performance analysis. Lighthouse/PageSpeed was not reachable, so browser-only metrics such as final LCP, CLS, and INP are estimated.",
    }


def fetch_json(url: str) -> Any:
    request = Request(
        url,
        headers={
            "User-Agent": "PerfMindAI/1.0",
            "Accept": "application/vnd.github+json",
        },
    )

    with urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8", errors="ignore"))


def fetch_text(url: str) -> str | None:
    request = Request(
        url,
        headers={
            "User-Agent": "PerfMindAI/1.0",
            "Accept": "application/vnd.github.raw+json,text/plain,*/*",
        },
    )

    try:
        with urlopen(request, timeout=15) as response:
            return response.read(800_000).decode("utf-8", errors="ignore")
    except Exception:
        return None


def parse_github_repo(repo_url: str) -> tuple[str, str]:
    parsed = urlparse(repo_url)
    parts = [part for part in parsed.path.strip("/").split("/") if part]

    if parsed.hostname != "github.com" or len(parts) < 2:
        raise HTTPException(status_code=400, detail="Enter a GitHub repository URL like https://github.com/user/repository")

    return parts[0], parts[1].removesuffix(".git")


def dependency_risks(package_json: dict[str, Any]) -> list[dict[str, str]]:
    dependencies = {
        **package_json.get("dependencies", {}),
        **package_json.get("devDependencies", {}),
    }
    heavy_packages = {
        "chart.js": "Chart.js can add a large client bundle. Lazy-load charts and keep them out of the landing route.",
        "moment": "Moment is large for date formatting. Prefer date-fns, dayjs, or native Intl APIs.",
        "lodash": "Import only specific lodash functions or replace small helpers with native JavaScript.",
        "three": "Three.js is expensive. Load 3D scenes only when the user reaches that feature.",
        "framer-motion": "Animation libraries can affect INP. Keep animations scoped and lazy-load heavy motion surfaces.",
        "antd": "Large UI libraries can inflate bundle size. Import components selectively and verify tree-shaking.",
        "bootstrap": "Global CSS can increase render cost. Keep only used styles and avoid unused components.",
    }

    findings = []
    for name, advice in heavy_packages.items():
        if name in dependencies:
            findings.append(
                {
                    "title": f"Potentially heavy dependency: {name}",
                    "impact": "Medium",
                    "evidence": f"`{name}` is listed in package.json.",
                    "fix": advice,
                }
            )

    return findings


def scan_repository(owner: str, repo: str) -> dict[str, Any]:
    repo_api = f"https://api.github.com/repos/{owner}/{repo}"
    repo_data = fetch_json(repo_api)
    default_branch = repo_data.get("default_branch", "main")
    tree_api = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{default_branch}?recursive=1"
    tree_data = fetch_json(tree_api)
    files = [item["path"] for item in tree_data.get("tree", []) if item.get("type") == "blob"]

    source_files = [
        path
        for path in files
        if path.endswith((".js", ".jsx", ".ts", ".tsx", ".css", ".scss", ".html"))
        and "node_modules/" not in path
        and ".next/" not in path
        and "dist/" not in path
    ]
    image_files = [path for path in files if path.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".avif"))]
    package_files = [path for path in files if path.endswith("package.json")]
    next_config = next((path for path in files if path in {"next.config.js", "next.config.mjs", "next.config.ts"} or path.endswith("/next.config.js") or path.endswith("/next.config.ts")), None)

    findings: list[dict[str, str]] = []
    inspected_files: list[str] = []
    package_summary: list[str] = []

    for package_path in package_files[:4]:
        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{default_branch}/{package_path}"
        raw = fetch_text(raw_url)
        if not raw:
            continue

        inspected_files.append(package_path)
        try:
            package_json = json.loads(raw)
        except json.JSONDecodeError:
            continue

        package_summary.append(package_path)
        findings.extend(dependency_risks(package_json))
        scripts = package_json.get("scripts", {})
        if "build" not in scripts:
            findings.append(
                {
                    "title": "No build script found",
                    "impact": "Low",
                    "evidence": f"{package_path} does not define a build script.",
                    "fix": "Add a repeatable build script so CI can run bundle and performance checks before deployment.",
                }
            )

    files_to_read = [
        path
        for path in source_files
        if any(token in path.lower() for token in ["page.", "layout.", "app.", "index.", "home", "hero", "banner", "image", "checkout"])
    ][:12]

    image_tag_without_dimensions = 0
    plain_img_usage = 0
    dynamic_import_usage = 0
    blocking_script_usage = 0

    for path in files_to_read:
        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{default_branch}/{path}"
        content = fetch_text(raw_url)
        if content is None:
            continue

        inspected_files.append(path)
        plain_img_usage += content.count("<img")
        dynamic_import_usage += content.count("dynamic(") + content.count("import(")
        blocking_script_usage += content.count("<script")

        if "<img" in content:
            rough_tags = content.split("<img")[1:]
            for tag in rough_tags:
                tag_head = tag.split(">", 1)[0]
                if "width=" not in tag_head or "height=" not in tag_head:
                    image_tag_without_dimensions += 1

    if plain_img_usage:
        findings.append(
            {
                "title": "Plain image tags found in source",
                "impact": "High" if image_tag_without_dimensions else "Medium",
                "evidence": f"Found {plain_img_usage} `<img>` usage across inspected files; {image_tag_without_dimensions} appear to miss width or height.",
                "fix": "Use optimized image components where available, add width/height or aspect-ratio, and lazy-load below-the-fold images.",
            }
        )

    if image_files and len(image_files) > 20:
        findings.append(
            {
                "title": "Large number of repository image assets",
                "impact": "Medium",
                "evidence": f"Found {len(image_files)} image assets in the repository.",
                "fix": "Compress large assets, prefer AVIF/WebP, and keep only route-critical images in the first load path.",
            }
        )

    if next_config is None and any(path.startswith("app/") or "/app/" in path or path.startswith("pages/") or "/pages/" in path for path in files):
        findings.append(
            {
                "title": "Next.js project has no visible next.config",
                "impact": "Low",
                "evidence": "App/pages routes were detected, but no next.config file was found in the scanned tree.",
                "fix": "Add image remote patterns, compression settings, and performance-safe configuration as the app grows.",
            }
        )

    if dynamic_import_usage == 0 and len(source_files) > 12:
        findings.append(
            {
                "title": "No dynamic imports found in inspected source files",
                "impact": "Medium",
                "evidence": f"Scanned {len(inspected_files)} files and did not find route-level dynamic imports.",
                "fix": "Lazy-load charts, dashboards, modals, maps, editors, and below-the-fold widgets with dynamic imports.",
            }
        )

    if blocking_script_usage:
        findings.append(
            {
                "title": "Script tags found in source",
                "impact": "Medium",
                "evidence": f"Found {blocking_script_usage} script tag usage in inspected files.",
                "fix": "Load third-party scripts after interaction or with framework script strategies instead of blocking the first render.",
            }
        )

    if not findings:
        findings.append(
            {
                "title": "No major repository performance smell found",
                "impact": "Low",
                "evidence": f"Scanned {len(files)} repository files and inspected {len(inspected_files)} relevant source/config files.",
                "fix": "Add Lighthouse CI and the PerfMind Web SDK to catch runtime regressions that static repo scanning cannot see.",
            }
        )

    risk_score = 20
    risk_score += min(25, len(image_files))
    risk_score += min(20, len(source_files) // 5)
    risk_score += 20 if any(item["impact"] == "High" for item in findings) else 0
    risk_score += 10 if any(item["impact"] == "Medium" for item in findings) else 0
    risk_score = min(100, risk_score)

    if risk_score >= 70:
        risk_level = "High"
    elif risk_score >= 40:
        risk_level = "Medium"
    else:
        risk_level = "Low"

    return {
        "repo": repo_data.get("full_name", f"{owner}/{repo}"),
        "description": repo_data.get("description"),
        "default_branch": default_branch,
        "language": repo_data.get("language"),
        "visibility": "Private" if repo_data.get("private") else "Public",
        "file_count": len(files),
        "source_file_count": len(source_files),
        "image_file_count": len(image_files),
        "package_files": package_summary,
        "inspected_files": inspected_files[:30],
        "findings": findings[:8],
        "risk_level": risk_level,
        "risk_score": risk_score,
        "recommendations": [
            "Run bundle analysis in CI and compare every pull request against the previous release.",
            "Add Lighthouse CI for synthetic checks and the Web Vitals SDK for field data.",
            "Use the website scan plus repository scan together before generating code patches.",
        ],
    }


@app.get("/")
def read_root():
    db_status = "Not configured"
    if engine:
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            db_status = "Connected to Neon Postgres!"
        except Exception as e:
            db_status = f"Connection failed: {str(e)}"

    return {
        "status": "ok",
        "message": "PerfMind AI API is running",
        "database_status": db_status,
    }


@app.post("/analyze")
def analyze_site(payload: AnalyzeRequest):
    url = str(payload.url)
    lighthouse_report = run_pagespeed_analysis(url)
    if lighthouse_report:
        try:
            request = Request(
                url,
                headers={
                    "User-Agent": "PerfMindAI/1.0 (+frontend-performance-monitoring-agent)",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                },
            )
            with urlopen(request, timeout=12) as response:
                html = response.read(2_000_000).decode("utf-8", errors="ignore")
            lighthouse_report["site_profile"] = infer_site_profile(url, html)
            lighthouse_report["business_suggestions"] = build_business_suggestions(url, html, lighthouse_report["summary"])
        except Exception:
            lighthouse_report["site_profile"] = {
                "type": "unknown",
                "confidence": 0.2,
                "needs_database": False,
                "database_reason": "HTML profile fetch failed",
                "signals": {},
            }
            lighthouse_report["business_suggestions"] = [
                suggestion(
                    "Connect GitHub for product-aware suggestions",
                    "Medium",
                    "PerfMind could run Lighthouse, but could not fetch enough HTML to classify the website type.",
                    "Scan the repository so the agent can infer whether the product needs backend models, database tables, and route-specific optimizations.",
                )
            ]
        return lighthouse_report

    request = Request(
        url,
        headers={
            "User-Agent": "PerfMindAI/1.0 (+frontend-performance-monitoring-agent)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )

    try:
        started = time.perf_counter()
        with urlopen(request, timeout=12) as response:
            ttfb_ms = int((time.perf_counter() - started) * 1000)
            content_type = response.headers.get("content-type", "")
            raw = response.read(2_000_000)
            load_ms = int((time.perf_counter() - started) * 1000)
            status_code = getattr(response, "status", 200)

        if "text/html" not in content_type and "application/xhtml" not in content_type and raw[:20].lstrip()[:1] != b"<":
            raise HTTPException(status_code=400, detail="The URL did not return an HTML page that PerfMind can analyze.")

        html = raw.decode("utf-8", errors="ignore")
        return analyze_html(url, html, ttfb_ms, load_ms, status_code)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Could not analyze this website: {e}")


@app.post("/github/analyze")
def analyze_github_repo(payload: GithubAnalyzeRequest):
    try:
        owner, repo = parse_github_repo(str(payload.repo_url))
        return scan_repository(owner, repo)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Could not scan this repository: {e}")
