# Folder Structure

```text
perfmind-ai/
  apps/
    web/
      app/
        (dashboard)/
          overview/
          metrics/
          regressions/
          deployments/
          root-cause/
          predictions/
          suggestions/
          chat/
        api/
      components/
        charts/
        dashboard/
        chat/
        layout/
      lib/
        api/
        auth/
        telemetry/
      styles/
      tests/
    api/
      perfmind_api/
        main.py
        core/
        db/
        models/
        schemas/
        routes/
        services/
        integrations/
        telemetry/
      migrations/
      tests/
    worker/
      perfmind_worker/
        main.py
        jobs/
        pipelines/
        schedulers/
        telemetry/
      tests/
  packages/
    web-sdk/
      src/
        collectors/
        transports/
        enrichers/
        vitals/
      tests/
    ai-agents/
      perfmind_agents/
        graph/
        agents/
        tools/
        prompts/
        evaluators/
      tests/
    shared-schemas/
      src/
        events/
        metrics/
        releases/
        incidents/
    ui/
      src/
        components/
        tokens/
  infra/
    docker/
    postgres/
    redis/
    otel/
    grafana/
    lighthouse/
    sentry/
  docs/
    architecture.md
    folder-structure.md
    database-schema.md
    api-routes.md
    agent-workflows.md
    ai-pipeline.md
    monitoring-setup.md
    implementation-plan.md
```

## Directory Responsibilities

`apps/web` contains the engineer-facing dashboard, charts, release views, AI suggestions, and chat assistant.

`apps/api` contains FastAPI routes, database models, service layer logic, integrations, authentication, and ingestion endpoints.

`apps/worker` contains background execution for aggregation, regression detection, prediction, root cause analysis, and notifications.

`packages/web-sdk` contains the installable browser SDK used by customer applications to collect Web Vitals, browser performance entries, API failures, errors, memory, and FPS samples.

`packages/ai-agents` contains LangGraph workflows, agent roles, prompts, tool adapters, and evaluation tests.

`packages/shared-schemas` contains shared TypeScript/Python-compatible event contracts. These schemas prevent dashboard, SDK, API, and worker drift.

`packages/ui` contains reusable dashboard UI primitives.

`infra` contains local and production infrastructure configuration.

`docs` contains the living system design.

