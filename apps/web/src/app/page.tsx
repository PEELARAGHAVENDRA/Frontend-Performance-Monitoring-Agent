"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

type ApiStatus = {
  status: string;
  message: string;
  database_status: string;
};

type AnalysisState = "idle" | "scanning" | "complete" | "error";
type GithubState = "idle" | "connecting" | "connected" | "error";

type AnalysisMetric = {
  label: string;
  value: string;
  unit: string;
  tone: "good" | "warn" | "bad" | "neutral";
};

type AnalysisIssue = {
  title: string;
  impact: "High" | "Medium" | "Low";
  evidence: string;
  fix: string;
};

type BusinessSuggestion = {
  title: string;
  priority: "High" | "Medium" | "Low";
  evidence: string;
  recommendation: string;
};

type WebsiteAnalysis = {
  scanner: string;
  url: string;
  title: string;
  status_code: number;
  site_profile?: {
    type: string;
    confidence: number;
    needs_database: boolean;
    database_reason: string;
    signals: Record<string, number>;
  };
  business_suggestions?: BusinessSuggestion[];
  summary: {
    html_bytes: number;
    image_count: number;
    script_count: number;
    stylesheet_count: number;
    blocking_script_count: number;
    missing_image_dimension_count: number;
    external_script_count: number;
  };
  metrics: AnalysisMetric[];
  issues: AnalysisIssue[];
  recommendations: string[];
  confidence: number;
  analysis_note: string;
};

type GitHubRepo = {
  repo: string;
  default_branch: string;
  description: string | null;
  language: string | null;
  visibility: string;
  file_count: number;
  source_file_count: number;
  image_file_count: number;
  package_files: string[];
  inspected_files: string[];
  findings: AnalysisIssue[];
  risk_level: "High" | "Medium" | "Low";
  risk_score: number;
  recommendations: string[];
};

const emptyMetrics: AnalysisMetric[] = [
  { label: "Performance Score", value: "--", unit: "", tone: "neutral" },
  { label: "LCP", value: "--", unit: "", tone: "neutral" },
  { label: "CLS", value: "--", unit: "", tone: "neutral" },
  { label: "INP", value: "--", unit: "", tone: "neutral" },
  { label: "TTFB", value: "--", unit: "", tone: "neutral" },
  { label: "Resources", value: "--", unit: "", tone: "neutral" },
];

function badgeClass(tone: string) {
  if (tone === "good") return "border-emerald-400/30 bg-emerald-400/10 text-emerald-200";
  if (tone === "warn") return "border-amber-400/30 bg-amber-400/10 text-amber-200";
  if (tone === "bad") return "border-rose-400/30 bg-rose-400/10 text-rose-200";
  return "border-slate-500/30 bg-slate-500/10 text-slate-200";
}

function impactClass(impact: string) {
  if (impact === "High") return badgeClass("bad");
  if (impact === "Medium") return badgeClass("warn");
  return badgeClass("good");
}

function formatBytes(bytes: number) {
  if (bytes > 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

function ApiConnectionCard() {
  const [apiStatus, setApiStatus] = useState<ApiStatus | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

    fetch(apiUrl)
      .then((response) => {
        if (!response.ok) throw new Error(`API returned ${response.status}`);
        return response.json();
      })
      .then((data: ApiStatus) => {
        setApiStatus(data);
        setError("");
      })
      .catch((fetchError: Error) => {
        setError(fetchError.message);
      });
  }, []);

  return (
    <section className="rounded-lg border border-slate-800 bg-slate-950 p-5">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-sm text-slate-400">System Status</p>
          <h2 className="mt-1 text-xl font-semibold text-white">FastAPI + Neon</h2>
        </div>
        <span className={`rounded-full border px-3 py-1 text-xs font-medium ${apiStatus ? badgeClass("good") : badgeClass("warn")}`}>
          {apiStatus ? "Connected" : "Checking"}
        </span>
      </div>
      <div className="mt-5 space-y-3 text-sm">
        <div className="flex justify-between gap-4 border-b border-slate-800 pb-3">
          <span className="text-slate-400">API</span>
          <span className="text-right text-slate-100">{apiStatus?.message || error || "Waiting for localhost:8000"}</span>
        </div>
        <div className="flex justify-between gap-4">
          <span className="text-slate-400">Database</span>
          <span className="text-right text-slate-100">{apiStatus?.database_status || "Start backend to verify Neon"}</span>
        </div>
      </div>
    </section>
  );
}

export default function Home() {
  const [websiteUrl, setWebsiteUrl] = useState("https://example.com");
  const [analysisState, setAnalysisState] = useState<AnalysisState>("idle");
  const [analysisError, setAnalysisError] = useState("");
  const [report, setReport] = useState<WebsiteAnalysis | null>(null);
  const [githubUrl, setGithubUrl] = useState("");
  const [githubState, setGithubState] = useState<GithubState>("idle");
  const [githubMessage, setGithubMessage] = useState("");
  const [githubRepo, setGithubRepo] = useState<GitHubRepo | null>(null);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const reportHost = useMemo(() => {
    try {
      return new URL(report?.url || websiteUrl).hostname;
    } catch {
      return "your website";
    }
  }, [report?.url, websiteUrl]);

  async function analyzeWebsite(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setAnalysisState("scanning");
    setAnalysisError("");
    setReport(null);

    try {
      const response = await fetch(`${apiUrl}/analyze`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ url: websiteUrl }),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || `Analysis failed with ${response.status}`);
      }

      setReport(data as WebsiteAnalysis);
      setAnalysisState("complete");
    } catch (error) {
      setAnalysisState("error");
      const message = error instanceof Error ? error.message : "Could not analyze this website.";
      setAnalysisError(
        message === "Failed to fetch"
          ? "Could not reach the FastAPI backend. Start http://127.0.0.1:8000, then run the analysis again."
          : message,
      );
    }
  }

  async function connectGithubRepo(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setGithubRepo(null);
    setGithubMessage("");
    setGithubState("connecting");

    try {
      const response = await fetch(`${apiUrl}/github/analyze`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ repo_url: githubUrl }),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || `Repository scan failed with ${response.status}`);
      }

      const repoData = data as GitHubRepo;
      setGithubRepo(repoData);
      setGithubMessage(`Scanned ${repoData.repo}. Found ${repoData.findings.length} source-level performance finding(s).`);
      setGithubState("connected");
    } catch (error) {
      setGithubState("error");
      const message = error instanceof Error ? error.message : "Could not scan repository.";
      setGithubMessage(
        message === "Failed to fetch"
          ? "Could not reach the FastAPI backend. Start http://127.0.0.1:8000, then scan the repository again."
          : message,
      );
    }
  }

  const hasReport = analysisState === "complete" && report;
  const metrics = report?.metrics || emptyMetrics;
  const issues = report?.issues || [];

  return (
    <main className="min-h-screen bg-[#07111f] text-slate-100">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-5 py-6 sm:px-8 lg:px-10">
        <header className="grid gap-6 border-b border-slate-800 pb-6 lg:grid-cols-[1.35fr_0.65fr] lg:items-end">
          <div>
            <p className="text-sm font-medium uppercase tracking-[0.18em] text-cyan-300">PerfMind AI</p>
            <h1 className="mt-3 max-w-4xl text-3xl font-semibold tracking-tight text-white sm:text-5xl">
              Paste a website. Get a real performance diagnosis.
            </h1>
            <p className="mt-4 max-w-3xl text-base leading-7 text-slate-300">
              PerfMind fetches the live URL through your FastAPI backend, inspects actual HTML, scripts, stylesheets, image attributes, and response timing, then asks for GitHub only when source-level fixes are needed.
            </p>
          </div>
          <ApiConnectionCard />
        </header>

        <section className="grid gap-6 lg:grid-cols-[1.15fr_0.85fr]">
          <section className="rounded-lg border border-cyan-400/25 bg-slate-950 p-5 shadow-2xl shadow-cyan-950/30">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="text-sm text-slate-400">Step 1</p>
                <h2 className="mt-1 text-2xl font-semibold text-white">Analyze a website URL</h2>
              </div>
              <span className="rounded-full border border-cyan-400/30 bg-cyan-400/10 px-3 py-1 text-xs font-medium text-cyan-200">
                Real backend scan
              </span>
            </div>

            <form onSubmit={analyzeWebsite} className="mt-6 flex flex-col gap-3 sm:flex-row">
              <input
                className="min-h-12 flex-1 rounded-md border border-slate-700 bg-slate-900 px-4 text-sm text-white outline-none placeholder:text-slate-500 focus:border-cyan-300"
                value={websiteUrl}
                onChange={(event) => setWebsiteUrl(event.target.value)}
                placeholder="https://your-website.com"
                type="url"
                required
              />
              <button
                className="min-h-12 rounded-md bg-cyan-300 px-6 text-sm font-semibold text-slate-950 transition hover:bg-cyan-200 disabled:cursor-not-allowed disabled:opacity-60"
                disabled={analysisState === "scanning"}
              >
                {analysisState === "scanning" ? "Analyzing..." : "Analyze Performance"}
              </button>
            </form>

            {analysisError ? (
              <div className="mt-4 rounded-md border border-rose-400/30 bg-rose-400/10 p-3 text-sm leading-6 text-rose-100">
                {analysisError}
              </div>
            ) : null}

            <div className="mt-6 grid gap-3 sm:grid-cols-3">
              {["HTML/resource scan", "Estimated Web Vitals", "Source-fix handoff"].map((item) => (
                <div key={item} className="rounded-lg border border-slate-800 bg-slate-900/70 p-4">
                  <p className="text-sm font-medium text-white">{item}</p>
                  <p className="mt-2 text-sm leading-6 text-slate-400">Generated from the submitted website.</p>
                </div>
              ))}
            </div>
          </section>

          <section className="rounded-lg border border-slate-800 bg-slate-950 p-5">
            <p className="text-sm text-slate-400">Product Flow</p>
            <h2 className="mt-1 text-2xl font-semibold text-white">How PerfMind works</h2>
            <div className="mt-5 space-y-4">
              {[
                "Scan the live website URL through the backend.",
                "Generate site-specific metrics and root-cause clues.",
                "Ask for GitHub only when exact source changes are needed.",
                "Turn findings into optimization patches after repo access.",
              ].map((step, index) => (
                <div key={step} className="flex gap-3 rounded-lg border border-slate-800 bg-slate-900/60 p-4">
                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-cyan-300 text-sm font-bold text-slate-950">{index + 1}</span>
                  <p className="text-sm leading-6 text-slate-200">{step}</p>
                </div>
              ))}
            </div>
          </section>
        </section>

        <section className={`grid gap-6 transition ${hasReport ? "opacity-100" : "opacity-80"} xl:grid-cols-[1fr_0.85fr]`}>
          <section className="rounded-lg border border-slate-800 bg-slate-950 p-5">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="text-sm text-slate-400">AI Website Report</p>
                <h2 className="mt-1 text-2xl font-semibold text-white">
                  {hasReport ? `Findings for ${reportHost}` : "Run a scan to generate findings"}
                </h2>
                {report?.title ? <p className="mt-1 text-sm text-slate-400">{report.title}</p> : null}
              </div>
              <span className={`rounded-full border px-3 py-1 text-xs font-medium ${hasReport ? badgeClass("warn") : badgeClass("neutral")}`}>
                {analysisState === "scanning" ? "Scanning" : hasReport ? `${report.scanner} · ${Math.round(report.confidence * 100)}%` : "Waiting"}
              </span>
            </div>

            <div className="mt-5 grid gap-4 md:grid-cols-3 xl:grid-cols-6">
              {metrics.map((metric) => (
                <article key={metric.label} className="rounded-lg border border-slate-800 bg-slate-900/70 p-4">
                  <p className="text-sm text-slate-400">{metric.label}</p>
                  <p className="mt-3 text-3xl font-semibold text-white">
                    {analysisState === "scanning" ? "..." : metric.value}
                    <span className="ml-1 text-base text-slate-400">{metric.unit}</span>
                  </p>
                  <span className={`mt-4 inline-flex rounded-full border px-2.5 py-1 text-xs ${badgeClass(metric.tone)}`}>
                    {metric.tone === "good" ? "Good" : metric.tone === "warn" ? "Watch" : metric.tone === "bad" ? "Fix" : "Pending"}
                  </span>
                </article>
              ))}
            </div>

            {report ? (
              <div className="mt-5 grid gap-3 rounded-lg border border-slate-800 bg-slate-900/50 p-4 text-sm sm:grid-cols-3">
                <div>
                  <p className="text-slate-400">HTML size</p>
                  <p className="mt-1 font-semibold text-white">{formatBytes(report.summary.html_bytes)}</p>
                </div>
                <div>
                  <p className="text-slate-400">Images without dimensions</p>
                  <p className="mt-1 font-semibold text-white">{report.summary.missing_image_dimension_count}</p>
                </div>
                <div>
                  <p className="text-slate-400">Blocking scripts</p>
                  <p className="mt-1 font-semibold text-white">{report.summary.blocking_script_count}</p>
                </div>
              </div>
            ) : null}

            <div className="mt-6 grid gap-4">
              {issues.length ? (
                issues.map((issue) => (
                  <article key={issue.title} className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                      <h3 className="text-lg font-semibold text-white">{issue.title}</h3>
                      <span className={`rounded-full border px-3 py-1 text-xs ${impactClass(issue.impact)}`}>{issue.impact} impact</span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-slate-300">{issue.evidence}</p>
                    <p className="mt-3 rounded-md border border-emerald-400/20 bg-emerald-400/10 p-3 text-sm leading-6 text-emerald-100">{issue.fix}</p>
                  </article>
                ))
              ) : (
                <article className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
                  <h3 className="text-lg font-semibold text-white">No scan yet</h3>
                  <p className="mt-3 text-sm leading-6 text-slate-300">
                    Enter a URL and PerfMind will generate findings based on the real page response.
                  </p>
                </article>
              )}
            </div>

            {report ? (
              <div className="mt-5 rounded-lg border border-cyan-400/20 bg-cyan-400/10 p-4 text-sm leading-6 text-cyan-50">
                {report.analysis_note}
              </div>
            ) : null}
          </section>

          <aside className="grid gap-6">
            <section className="rounded-lg border border-slate-800 bg-slate-950 p-5">
              <p className="text-sm text-slate-400">Smart Suggestions</p>
              <h2 className="mt-1 text-2xl font-semibold text-white">How this website can improve</h2>
              {report?.site_profile ? (
                <div className="mt-4 rounded-lg border border-slate-800 bg-slate-900/70 p-4 text-sm">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <p className="text-slate-400">Detected website type</p>
                      <p className="mt-1 text-lg font-semibold capitalize text-white">{report.site_profile.type}</p>
                    </div>
                    <span className={`rounded-full border px-3 py-1 text-xs ${report.site_profile.needs_database ? badgeClass("warn") : badgeClass("good")}`}>
                      {report.site_profile.needs_database ? "Database likely needed" : "Database optional"}
                    </span>
                  </div>
                  <p className="mt-3 leading-6 text-slate-300">
                    Confidence {Math.round(report.site_profile.confidence * 100)}%. Reason: {report.site_profile.database_reason}.
                  </p>
                </div>
              ) : (
                <div className="mt-4 rounded-lg border border-slate-800 bg-slate-900/70 p-4 text-sm leading-6 text-slate-300">
                  Run a website scan to get product-aware suggestions.
                </div>
              )}

              <div className="mt-4 space-y-3">
                {(report?.business_suggestions || [
                  {
                    title: "Waiting for website analysis",
                    priority: "Medium" as const,
                    evidence: "PerfMind needs a real URL scan before it can classify the site.",
                    recommendation: "Analyze a website URL first, then this box will show contextual suggestions.",
                  },
                ]).map((item) => (
                  <article key={item.title} className="rounded-md border border-slate-800 bg-slate-900/70 p-3 text-sm leading-6">
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                      <p className="font-semibold text-white">{item.title}</p>
                      <span className={`rounded-full border px-2.5 py-1 text-xs ${impactClass(item.priority)}`}>{item.priority}</span>
                    </div>
                    <p className="mt-2 text-slate-300">{item.evidence}</p>
                    <p className="mt-2 text-cyan-100">{item.recommendation}</p>
                  </article>
                ))}
              </div>
            </section>

            <section className="rounded-lg border border-slate-800 bg-slate-950 p-5">
              <p className="text-sm text-slate-400">Step 2</p>
                <h2 className="mt-1 text-2xl font-semibold text-white">Scan GitHub for exact fixes</h2>
              <p className="mt-3 text-sm leading-6 text-slate-300">
                The URL scan detects symptoms. GitHub access lets the agent inspect files and turn the report into exact source-level improvements.
              </p>
              <form onSubmit={connectGithubRepo} className="mt-5 flex flex-col gap-3">
                <input
                  className="min-h-11 rounded-md border border-slate-700 bg-slate-900 px-3 text-sm text-white outline-none placeholder:text-slate-500 focus:border-cyan-300"
                  value={githubUrl}
                  onChange={(event) => setGithubUrl(event.target.value)}
                  placeholder="https://github.com/user/repository"
                  type="url"
                />
                <button
                  className="min-h-11 rounded-md border border-cyan-400/30 bg-cyan-400/10 px-5 text-sm font-semibold text-cyan-100 transition hover:bg-cyan-400/20 disabled:cursor-not-allowed disabled:opacity-60"
                  disabled={githubState === "connecting"}
                >
                  {githubState === "connecting" ? "Scanning repository..." : "Scan Repository"}
                </button>
              </form>
              {githubMessage ? (
                <div className={`mt-4 rounded-md border p-3 text-sm leading-6 ${githubState === "connected" ? "border-emerald-400/30 bg-emerald-400/10 text-emerald-100" : "border-rose-400/30 bg-rose-400/10 text-rose-100"}`}>
                  {githubMessage}
                </div>
              ) : null}
              {githubRepo ? (
                <div className="mt-4 grid gap-3 rounded-lg border border-slate-800 bg-slate-900/70 p-4 text-sm sm:grid-cols-2">
                  <div>
                    <p className="text-slate-400">Default branch</p>
                    <p className="mt-1 font-medium text-white">{githubRepo.default_branch}</p>
                  </div>
                  <div>
                    <p className="text-slate-400">Language</p>
                    <p className="mt-1 font-medium text-white">{githubRepo.language || "Mixed"}</p>
                  </div>
                  <div>
                    <p className="text-slate-400">Visibility</p>
                    <p className="mt-1 font-medium text-white">{githubRepo.visibility}</p>
                  </div>
                  <div>
                    <p className="text-slate-400">Risk</p>
                    <p className="mt-1 font-medium text-white">{githubRepo.risk_level} ({githubRepo.risk_score}/100)</p>
                  </div>
                  <div>
                    <p className="text-slate-400">Files scanned</p>
                    <p className="mt-1 font-medium text-white">{githubRepo.file_count} total</p>
                  </div>
                  <div>
                    <p className="text-slate-400">Source files</p>
                    <p className="mt-1 font-medium text-white">{githubRepo.source_file_count}</p>
                  </div>
                  <div>
                    <p className="text-slate-400">Image assets</p>
                    <p className="mt-1 font-medium text-white">{githubRepo.image_file_count}</p>
                  </div>
                </div>
              ) : null}
              {githubRepo ? (
                <div className="mt-5 space-y-4">
                  <div>
                    <p className="text-sm font-semibold text-white">Repository findings</p>
                    <div className="mt-3 space-y-3">
                      {githubRepo.findings.map((finding) => (
                        <article key={finding.title} className="rounded-md border border-slate-800 bg-slate-900/70 p-3 text-sm leading-6">
                          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                            <p className="font-semibold text-white">{finding.title}</p>
                            <span className={`rounded-full border px-2.5 py-1 text-xs ${impactClass(finding.impact)}`}>{finding.impact}</span>
                          </div>
                          <p className="mt-2 text-slate-300">{finding.evidence}</p>
                          <p className="mt-2 text-emerald-100">{finding.fix}</p>
                        </article>
                      ))}
                    </div>
                  </div>
                  <div className="rounded-lg border border-slate-800 bg-slate-900/70 p-4">
                    <p className="text-sm font-semibold text-white">Inspected files</p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {githubRepo.inspected_files.length ? (
                        githubRepo.inspected_files.slice(0, 12).map((file) => (
                          <span key={file} className="rounded-full border border-slate-700 bg-slate-950 px-3 py-1 text-xs text-slate-300">
                            {file}
                          </span>
                        ))
                      ) : (
                        <span className="text-sm text-slate-400">No readable source files were inspected.</span>
                      )}
                    </div>
                  </div>
                </div>
              ) : (
                <ul className="mt-5 space-y-3">
                  {[
                    "PerfMind will read public repository metadata and source tree.",
                    "It checks package.json dependencies, source files, images, script usage, and config signals.",
                    "For private repos, add a GitHub token integration in the backend.",
                  ].map((finding) => (
                    <li key={finding} className="rounded-md border border-slate-800 bg-slate-900/70 p-3 text-sm leading-6 text-slate-200">
                      {finding}
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className="rounded-lg border border-slate-800 bg-slate-950 p-5">
              <p className="text-sm text-slate-400">Recommendations</p>
              <h2 className="mt-1 text-2xl font-semibold text-white">Next actions</h2>
              <ul className="mt-5 space-y-3">
                {(report?.recommendations || ["Run a website scan first.", "Then connect GitHub for code-aware fixes.", "Add Web Vitals SDK for continuous monitoring."]).map((item) => (
                  <li key={item} className="rounded-md border border-slate-800 bg-slate-900/70 p-3 text-sm leading-6 text-slate-200">
                    {item}
                  </li>
                ))}
              </ul>
            </section>
          </aside>
        </section>
      </div>
    </main>
  );
}
