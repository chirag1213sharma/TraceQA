"use client";

import {
  Activity,
  Clock3,
  LoaderCircle,
  Play,
  RefreshCw,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import useSWR from "swr";

import { EmptyState, ErrorState, LoadingState } from "@/components/data-state";
import { PageIntro } from "@/components/page-intro";
import { StatusBadge } from "@/components/status-badge";
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  DashboardData,
  getDashboardData,
  ingestTestReports,
  TestRun,
} from "@/lib/api";

function formatDate(value: string, compact = false) {
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    ...(compact ? {} : { hour: "2-digit", minute: "2-digit" }),
  }).format(new Date(value));
}

function formatDuration(seconds: number) {
  if (seconds < 60) {
    return `${seconds.toFixed(1)}s`;
  }
  return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
}

function testNameForRun(run: TestRun) {
  if (!run.source_file) {
    return `Run #${run.id}`;
  }
  const [testName] = run.source_file.split(/[\\/]/);
  return testName || `Run #${run.id}`;
}

function countFromRatio(value: string | null | undefined) {
  if (!value) return 0;
  const count = Number.parseInt(value.split("/", 1)[0].trim(), 10);
  return Number.isFinite(count) ? count : 0;
}

export default function DashboardPage() {
  const { data, error, isLoading, mutate } = useSWR<DashboardData>(
    "traceqa-dashboard",
    getDashboardData,
  );
  const [selectedRun, setSelectedRun] = useState<TestRun | null>(null);
  const [isIngesting, setIsIngesting] = useState(false);
  const [ingestionMessage, setIngestionMessage] = useState<{
    tone: "success" | "error";
    text: string;
  } | null>(null);

  const view = useMemo(() => {
    const runs = data?.runs ?? [];
    const results = data?.results ?? [];
    const insights = data?.insights ?? [];
    const resultsByRun = new Map(
      runs.map((run) => [
        run.id,
        results.filter((result) => result.run_id === run.id),
      ]),
    );
    const insightByRun = new Map(
      insights.map((insight) => [insight.run_id, insight]),
    );
    const passed = insights.reduce(
      (sum, insight) => sum + countFromRatio(insight.test_cases_passed),
      0,
    );
    const failed = insights.reduce(
      (sum, insight) => sum + countFromRatio(insight.test_cases_failed),
      0,
    );
    const passRate = passed + failed ? (passed / (passed + failed)) * 100 : 0;
    const totalDuration = results.reduce(
      (sum, result) => sum + result.execution_time,
      0,
    );
    const trend = [...runs]
      .reverse()
      .slice(-12)
      .map((run) => {
        const insight = insightByRun.get(run.id);
        return {
          date: formatDate(run.timestamp, true),
          passed: countFromRatio(insight?.test_cases_passed),
          failed: countFromRatio(insight?.test_cases_failed),
        };
      });

    return {
      runs,
      results,
      resultsByRun,
      insightByRun,
      passRate,
      passed,
      failed,
      totalDuration,
      trend,
    };
  }, [data]);

  async function runIngestion() {
    setIsIngesting(true);
    setIngestionMessage(null);
    try {
      await ingestTestReports();
      await mutate();
      setIngestionMessage({
        tone: "success",
        text: "Test reports were ingested and analyzed successfully.",
      });
    } catch (requestError) {
      setIngestionMessage({
        tone: "error",
        text:
          requestError instanceof Error
            ? requestError.message
            : "Test report ingestion failed.",
      });
    } finally {
      setIsIngesting(false);
    }
  }

  const selectedResults = selectedRun
    ? (view.resultsByRun.get(selectedRun.id) ?? [])
    : [];
  const selectedInsight = selectedRun
    ? view.insightByRun.get(selectedRun.id)
    : undefined;

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
        <PageIntro
          eyebrow="Test observability"
          title="Quality signals, without the noise."
          description="Monitor automation health, execution trends, and AI findings from a single operational view."
        />
        <div className="flex shrink-0 gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => mutate()}
            disabled={isLoading}
          >
            <RefreshCw className="size-4" aria-hidden="true" />
            Refresh
          </Button>
          <Button
            type="button"
            size="sm"
            onClick={runIngestion}
            disabled={isIngesting}
          >
            {isIngesting ? (
              <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />
            ) : (
              <Play className="size-4" aria-hidden="true" />
            )}
            Ingest now
          </Button>
        </div>
      </div>

      {ingestionMessage ? (
        <Alert variant={ingestionMessage.tone === "error" ? "destructive" : "default"}>
          {ingestionMessage.tone === "success" ? (
            <ShieldCheck aria-hidden="true" />
          ) : (
            <Activity aria-hidden="true" />
          )}
          <AlertTitle>
            {ingestionMessage.tone === "success"
              ? "Ingestion complete"
              : "Ingestion failed"}
          </AlertTitle>
          <AlertDescription>{ingestionMessage.text}</AlertDescription>
        </Alert>
      ) : null}

      {isLoading ? <LoadingState /> : null}
      {error ? (
        <ErrorState
          error={error instanceof Error ? error : new Error("Unknown API error")}
          onRetry={() => mutate()}
        />
      ) : null}

      {data && !error ? (
        <>
          <section
            aria-label="Quality metrics"
            className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"
          >
            <MetricCard
              label="Pass rate"
              value={`${view.passRate.toFixed(1)}%`}
              detail={`${view.passed} passing tests`}
              icon={ShieldCheck}
            />
            <MetricCard
              label="Failed tests"
              value={String(view.failed)}
              detail="Across analyzed reports"
              icon={Sparkles}
            />
            <MetricCard
              label="Observed runs"
              value={String(view.runs.length)}
              detail="Most recent 100 runs"
              icon={Activity}
            />
            <MetricCard
              label="Execution time"
              value={formatDuration(view.totalDuration)}
              detail="Across loaded results"
              icon={Clock3}
            />
          </section>

          {view.runs.length ? (
            <>
              <section className="grid gap-4 xl:grid-cols-2">
                <TrendCard
                  title="Tests passed"
                  description="Passed test cases reported by Gemini for each run"
                  data={view.trend}
                  dataKey="passed"
                  color="var(--chart-1)"
                  unit=""
                />
                <TrendCard
                  title="Tests failed"
                  description="Failed test cases reported by Gemini for each run"
                  data={view.trend}
                  dataKey="failed"
                  color="var(--chart-2)"
                  unit=""
                />
              </section>

              <Card>
                <CardHeader>
                  <CardTitle>Recent test runs</CardTitle>
                  <CardDescription>
                    Select a run to inspect its test logs and AI analysis.
                  </CardDescription>
                </CardHeader>
                <CardContent className="px-0">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="pl-6">Run</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Tests</TableHead>
                        <TableHead>Pass rate</TableHead>
                        <TableHead>Duration</TableHead>
                        <TableHead className="pr-6">Source</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {view.runs.slice(0, 12).map((run) => {
                        const runResults = view.resultsByRun.get(run.id) ?? [];
                        const insight = view.insightByRun.get(run.id);
                        const passing = countFromRatio(insight?.test_cases_passed);
                        const failing = countFromRatio(insight?.test_cases_failed);
                        const duration = runResults.reduce(
                          (sum, item) => sum + item.execution_time,
                          0,
                        );
                        return (
                          <TableRow
                            key={run.id}
                            tabIndex={0}
                            className="cursor-pointer"
                            onClick={() => setSelectedRun(run)}
                            onKeyDown={(event) => {
                              if (event.key === "Enter" || event.key === " ") {
                                event.preventDefault();
                                setSelectedRun(run);
                              }
                            }}
                          >
                            <TableCell className="pl-6 font-medium">
                              <span className="block">{testNameForRun(run)}</span>
                              <span className="mt-0.5 block text-xs font-normal text-muted-foreground">
                                {formatDate(run.timestamp)} · Run #{run.id}
                              </span>
                            </TableCell>
                            <TableCell>
                              <StatusBadge value={run.run_status} />
                            </TableCell>
                            <TableCell>{passing + failing || runResults.length}</TableCell>
                            <TableCell>
                              {passing + failing
                                ? `${((passing / (passing + failing)) * 100).toFixed(0)}%`
                                : "—"}
                            </TableCell>
                            <TableCell>{formatDuration(duration)}</TableCell>
                            <TableCell className="max-w-48 truncate pr-6 text-muted-foreground">
                              {run.source_file ?? run.source_drive}
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            </>
          ) : (
            <EmptyState
              title="No test runs yet"
              description="Configure the test log directory in Settings, then select Ingest now to create the first observable run."
            />
          )}
        </>
      ) : null}

      <Dialog
        open={selectedRun !== null}
        onOpenChange={(open) => {
          if (!open) setSelectedRun(null);
        }}
      >
        <DialogContent className="max-h-[88vh] overflow-y-auto sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle>
              {selectedRun ? testNameForRun(selectedRun) : "Test run"}
            </DialogTitle>
            <DialogDescription>
              {selectedRun ? formatDate(selectedRun.timestamp) : ""} ·{" "}
              {selectedRun?.source_file ?? selectedRun?.source_drive}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-6">
            <section className="rounded-lg border bg-muted/30 p-4">
              <div className="flex items-center gap-2">
                <Sparkles className="size-4 text-primary" aria-hidden="true" />
                <h3 className="text-sm font-semibold">AI analysis</h3>
              </div>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                {selectedInsight?.ai_analysis ??
                  selectedInsight?.summary ??
                  "No AI analysis is available for this run."}
              </p>
            </section>

            <section className="rounded-lg border border-primary/20 bg-primary/5 p-4">
              <h3 className="text-sm font-semibold">Instructions for QA</h3>
              {selectedInsight?.instruction_to_qa.length ? (
                <ol className="mt-2 list-decimal space-y-2 pl-5 text-sm leading-6 text-muted-foreground">
                  {selectedInsight.instruction_to_qa.map((instruction, index) => (
                    <li key={`${selectedInsight.id}-${index}`}>{instruction}</li>
                  ))}
                </ol>
              ) : (
                <p className="mt-2 text-sm leading-6 text-muted-foreground">
                  No QA instructions are available for this run.
                </p>
              )}
            </section>

            <section>
              <h3 className="mb-3 text-sm font-semibold">Run summary</h3>
              <div className="overflow-hidden rounded-lg border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Passed</TableHead>
                      <TableHead>Failed</TableHead>
                      <TableHead>Failed suites or tests</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    <TableRow>
                      <TableCell>{selectedInsight?.test_cases_passed ?? "—"}</TableCell>
                      <TableCell>{selectedInsight?.test_cases_failed ?? "—"}</TableCell>
                      <TableCell className="max-w-md">
                        {selectedInsight?.failed_test_case_list.length
                          ? selectedInsight.failed_test_case_list.join(", ")
                          : "None"}
                      </TableCell>
                    </TableRow>
                  </TableBody>
                </Table>
              </div>
            </section>

            <section>
              <h3 className="mb-3 text-sm font-semibold">Raw failure logs</h3>
              <div className="space-y-3">
                {selectedResults.some((result) => result.error_log) ? (
                  selectedResults
                    .filter((result) => result.error_log)
                    .map((result) => (
                      <div key={result.id} className="overflow-hidden rounded-lg border">
                        <p className="border-b bg-muted/50 px-3 py-2 font-mono text-xs font-medium">
                          {result.test_name}
                        </p>
                        <pre className="overflow-x-auto whitespace-pre-wrap p-3 font-mono text-xs leading-5 text-muted-foreground">
                          {result.error_log}
                        </pre>
                      </div>
                    ))
                ) : (
                  <p className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
                    This run contains no failure logs.
                  </p>
                )}
              </div>
            </section>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function MetricCard({
  label,
  value,
  detail,
  icon: Icon,
}: {
  label: string;
  value: string;
  detail: string;
  icon: typeof Activity;
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardDescription>{label}</CardDescription>
        <Icon className="size-4 text-primary" aria-hidden="true" />
      </CardHeader>
      <CardContent>
        <p className="text-2xl font-semibold tracking-tight">{value}</p>
        <p className="mt-1 text-xs text-muted-foreground">{detail}</p>
      </CardContent>
    </Card>
  );
}

function TrendCard({
  title,
  description,
  data,
  dataKey,
  color,
  unit,
}: {
  title: string;
  description: string;
  data: Array<Record<string, string | number>>;
  dataKey: string;
  color: string;
  unit: string;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="h-56 w-full">
          <ResponsiveContainer
            width="100%"
            height="100%"
            initialDimension={{ width: 640, height: 224 }}
          >
            <AreaChart data={data} margin={{ left: -18, right: 8 }}>
              <defs>
                <linearGradient id={`${dataKey}-fill`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={color} stopOpacity={0.3} />
                  <stop offset="95%" stopColor={color} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" vertical={false} opacity={0.25} />
              <XAxis dataKey="date" tickLine={false} axisLine={false} fontSize={11} />
              <YAxis
                domain={[0, "auto"]}
                tickLine={false}
                axisLine={false}
                fontSize={11}
                unit={unit}
              />
              <Tooltip
                formatter={(value) => [`${value}${unit}`, title]}
                contentStyle={{
                  borderRadius: "0.75rem",
                  borderColor: "var(--border)",
                  background: "var(--card)",
                  color: "var(--card-foreground)",
                  fontSize: "0.75rem",
                }}
              />
              <Area
                type="monotone"
                dataKey={dataKey}
                stroke={color}
                strokeWidth={2}
                fill={`url(#${dataKey}-fill)`}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
