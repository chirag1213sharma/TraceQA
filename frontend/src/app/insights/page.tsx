"use client";

import {
  AlertTriangle,
  BrainCircuit,
  Gauge,
  Lightbulb,
} from "lucide-react";
import { useMemo } from "react";
import useSWR from "swr";

import { EmptyState, ErrorState, LoadingState } from "@/components/data-state";
import { PageIntro } from "@/components/page-intro";
import { StatusBadge } from "@/components/status-badge";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { DashboardData, getDashboardData } from "@/lib/api";

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export default function InsightsPage() {
  const { data, error, isLoading, mutate } = useSWR<DashboardData>(
    "traceqa-dashboard",
    getDashboardData,
  );

  const intelligence = useMemo(() => {
    const runs = data?.runs ?? [];
    const insights = data?.insights ?? [];
    const runById = new Map(runs.map((run) => [run.id, run]));
    const failedRuns = insights.filter((insight) => insight.status === "failed").length;
    const failedCases = insights.reduce((total, insight) => {
      const failed = Number.parseInt(
        insight.test_cases_failed?.split("/", 1)[0] ?? "0",
        10,
      );
      return total + (Number.isFinite(failed) ? failed : 0);
    }, 0);

    return {
      insights,
      runById,
      failedRuns,
      failedCases,
    };
  }, [data]);

  return (
    <div className="space-y-8">
      <PageIntro
        eyebrow="Test intelligence"
        title="AI Insights"
        description="Gemini analysis and prioritized QA actions for every observed test run."
      />

      {isLoading ? <LoadingState label="Loading AI intelligence" /> : null}
      {error ? (
        <ErrorState
          error={error instanceof Error ? error : new Error("Unknown API error")}
          onRetry={() => mutate()}
        />
      ) : null}

      {data && !error ? (
        intelligence.insights.length ? (
          <>
            <section
              aria-label="Intelligence metrics"
              className="grid gap-4 sm:grid-cols-3"
            >
              <InsightMetric
                icon={BrainCircuit}
                label="AI analyses"
                value={String(intelligence.insights.length)}
                detail="Structured run assessments"
              />
              <InsightMetric
                icon={AlertTriangle}
                label="Failed runs"
                value={String(intelligence.failedRuns)}
                detail="Runs requiring investigation"
              />
              <InsightMetric
                icon={Lightbulb}
                label="Failed test cases"
                value={String(intelligence.failedCases)}
                detail="Across analyzed reports"
              />
            </section>

            <section>
              <div className="mb-4">
                <h2 className="text-lg font-semibold tracking-tight">
                  Recent analyses
                </h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  Test outcomes, AI findings, and prioritized QA instructions.
                </p>
              </div>
              <div className="grid gap-4 lg:grid-cols-2">
                {intelligence.insights.map((insight) => {
                  const run = intelligence.runById.get(insight.run_id);
                  return (
                    <Card key={insight.id}>
                      <CardHeader>
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <CardTitle>
                              {insight.test_name ?? `Run #${insight.run_id}`}
                            </CardTitle>
                            <CardDescription>
                              {run ? formatDate(run.timestamp) : "Run metadata unavailable"}
                            </CardDescription>
                          </div>
                          <StatusBadge value={insight.status ?? run?.run_status ?? "unknown"} />
                        </div>
                      </CardHeader>
                      <CardContent className="space-y-4">
                        <p className="text-sm leading-6 text-muted-foreground">
                          {insight.ai_analysis ?? insight.summary}
                        </p>
                        <div className="rounded-lg border border-primary/20 bg-primary/5 p-3">
                          <p className="text-xs font-semibold">Instructions for QA</p>
                          {insight.instruction_to_qa.length ? (
                            <ol className="mt-2 list-decimal space-y-1 pl-4 text-xs leading-5 text-muted-foreground">
                              {insight.instruction_to_qa.map((instruction, index) => (
                                <li key={`${insight.id}-${index}`}>{instruction}</li>
                              ))}
                            </ol>
                          ) : (
                            <p className="mt-2 text-xs leading-5 text-muted-foreground">
                              No QA instructions are available.
                            </p>
                          )}
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <Badge variant="outline">
                            Passed: {insight.test_cases_passed ?? "—"}
                          </Badge>
                          <Badge variant="outline">
                            Failed: {insight.test_cases_failed ?? "—"}
                          </Badge>
                        </div>
                        {insight.failed_test_case_list.length ? (
                          <p className="text-xs leading-5 text-muted-foreground">
                            <span className="font-semibold text-foreground">
                              Failed suites:{" "}
                            </span>
                            {insight.failed_test_case_list.join(", ")}
                          </p>
                        ) : null}
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            </section>
          </>
        ) : (
          <EmptyState
            title="No AI insights yet"
            description="Ingest a test run from the Dashboard to generate Gemini analysis and QA instructions."
          />
        )
      ) : null}
    </div>
  );
}

function InsightMetric({
  icon: Icon,
  label,
  value,
  detail,
}: {
  icon: typeof Gauge;
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <Card>
      <CardContent className="flex items-center gap-4 p-5">
        <span className="flex size-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
          <Icon className="size-5" aria-hidden="true" />
        </span>
        <div>
          <p className="text-2xl font-semibold tracking-tight">{value}</p>
          <p className="text-sm font-medium">{label}</p>
          <p className="mt-0.5 text-xs text-muted-foreground">{detail}</p>
        </div>
      </CardContent>
    </Card>
  );
}
