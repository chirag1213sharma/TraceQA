# TraceQA Frontend

The TraceQA interface is a Next.js App Router application using TypeScript,
Tailwind CSS, shadcn/ui, and `next-themes`.

## Run locally

```powershell
cd C:\TraceQA\frontend
npm install
Copy-Item .env.local.example .env.local
npm run dev
```

Open `http://localhost:3000`. The integrated application includes:

- A responsive, collapsible sidebar with Dashboard, AI Insights, Commit Radar,
  and Settings navigation.
- A mobile navigation drawer.
- Persistent light and dark themes that default to the operating-system theme.
- Dashboard metrics, pass-rate and flakiness trend charts, recent runs, and
  detailed log/AI dialogs.
- Predictive AI insight cards and proactive fixes.
- Branch-filtered commit regression analysis and generated test plans.
- Masked runtime configuration forms for ingestion, GitHub, and LiteLLM.

The default AI provider is the local Ollama server at
`http://localhost:11434`, using `mistral:7b-instruct` through the LiteLLM model
identifier `ollama/mistral:7b-instruct`. No LLM API key is required for this
default configuration.

Set `NEXT_PUBLIC_TRACEQA_API_URL` when the FastAPI service is not available at
`http://localhost:8000/api/v1`.

## Validation

```powershell
npm run lint
npm run build
```
