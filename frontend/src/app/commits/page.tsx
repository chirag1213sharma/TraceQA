"use client";

import {
  Beaker,
  CheckCircle2,
  GitBranch,
  GitCommitHorizontal,
  ListChecks,
  RefreshCw,
  ShieldAlert,
} from "lucide-react";
import { useMemo, useState } from "react";
import useSWR from "swr";

import { EmptyState, ErrorState, LoadingState } from "@/components/data-state";
import { PageIntro } from "@/components/page-intro";
import { StatusBadge } from "@/components/status-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { CommitImpact, getCommitImpacts } from "@/lib/api";
import { cn } from "@/lib/utils";

export default function CommitsPage() {
  const { data, error, isLoading, mutate } = useSWR<CommitImpact[]>(
    "traceqa-commits",
    getCommitImpacts,
  );
  const [branch, setBranch] = useState("main");
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const branches = useMemo(() => {
    const values = new Set((data ?? []).map((impact) => impact.branch));
    if (!values.has("main")) values.add("main");
    return [...values].sort((left, right) => {
      if (left === "main") return -1;
      if (right === "main") return 1;
      return left.localeCompare(right);
    });
  }, [data]);
  const filtered = (data ?? []).filter((impact) => impact.branch === branch);
  const selected =
    filtered.find((impact) => impact.id === selectedId) ?? filtered[0] ?? null;

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
        <PageIntro
          eyebrow="Impact analysis"
          title="Commit Radar"
          description="Understand regression risk and focus test coverage before a change reaches production."
        />
        <div className="flex items-center gap-2">
          <label htmlFor="branch" className="sr-only">
            Select branch
          </label>
          <div className="relative">
            <GitBranch
              className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden="true"
            />
            <select
              id="branch"
              value={branch}
              onChange={(event) => {
                setBranch(event.target.value);
                setSelectedId(null);
              }}
              className="h-9 min-w-40 appearance-none rounded-md border bg-background py-1 pl-9 pr-8 text-sm font-medium outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {branches.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </div>
          <Button
            type="button"
            size="icon-sm"
            variant="outline"
            onClick={() => mutate()}
            aria-label="Refresh commits"
          >
            <RefreshCw className="size-4" aria-hidden="true" />
          </Button>
        </div>
      </div>

      {isLoading ? <LoadingState label="Loading commit impact analyses" /> : null}
      {error ? (
        <ErrorState
          error={error instanceof Error ? error : new Error("Unknown API error")}
          onRetry={() => mutate()}
        />
      ) : null}

      {data && !error ? (
        filtered.length ? (
          <div className="grid gap-5 xl:grid-cols-[360px_minmax(0,1fr)]">
            <Card className="h-fit">
              <CardHeader>
                <CardTitle>Recent commits</CardTitle>
                <CardDescription>
                  {filtered.length} analyzed on {branch}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                {filtered.map((impact) => (
                  <button
                    key={impact.id}
                    type="button"
                    onClick={() => setSelectedId(impact.id)}
                    className={cn(
                      "w-full rounded-lg border p-3 text-left transition-colors hover:bg-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                      selected?.id === impact.id
                        ? "border-primary/30 bg-primary/5"
                        : "bg-background",
                    )}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <span className="inline-flex items-center gap-2 font-mono text-xs font-semibold">
                        <GitCommitHorizontal
                          className="size-3.5 text-primary"
                          aria-hidden="true"
                        />
                        {impact.commit_hash.slice(0, 10)}
                      </span>
                      <StatusBadge value={impact.regression_risk_level} />
                    </div>
                    <p className="mt-3 line-clamp-2 text-sm leading-5 text-muted-foreground">
                      {impact.summary}
                    </p>
                  </button>
                ))}
              </CardContent>
            </Card>

            {selected ? <CommitDetail impact={selected} /> : null}
          </div>
        ) : (
          <EmptyState
            title={`No analyzed commits on ${branch}`}
            description="Configure the GitHub webhook in Settings and push a commit to generate the first regression impact analysis."
          />
        )
      ) : null}
    </div>
  );
}

function CommitDetail({ impact }: { impact: CommitImpact }) {
  return (
    <div className="space-y-5">
      <Card>
        <CardHeader>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <div className="mb-2 flex items-center gap-2">
                <Badge variant="outline" className="font-mono">
                  {impact.commit_hash.slice(0, 12)}
                </Badge>
                <Badge variant="secondary">
                  <GitBranch className="size-3" aria-hidden="true" />
                  {impact.branch}
                </Badge>
              </div>
              <CardTitle>Regression impact</CardTitle>
              <CardDescription className="mt-2 max-w-2xl leading-6">
                {impact.summary}
              </CardDescription>
            </div>
            <div className="flex items-center gap-2 rounded-lg border bg-muted/30 px-3 py-2">
              <ShieldAlert className="size-4 text-primary" aria-hidden="true" />
              <span className="text-xs text-muted-foreground">Risk</span>
              <StatusBadge value={impact.regression_risk_level} />
            </div>
          </div>
        </CardHeader>
      </Card>

      <section className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Beaker className="size-4 text-primary" aria-hidden="true" />
              <CardTitle>Automated test plan</CardTitle>
            </div>
            <CardDescription>
              Existing tests recommended for this change.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {impact.suggested_automated_tests.length ? (
              <ul className="space-y-2">
                {impact.suggested_automated_tests.map((test, index) => (
                  <li
                    key={`${test}-${index}`}
                    className="flex items-start gap-2 rounded-lg border bg-muted/20 p-3"
                  >
                    <CheckCircle2
                      className="mt-0.5 size-4 shrink-0 text-emerald-600 dark:text-emerald-400"
                      aria-hidden="true"
                    />
                    <code className="break-all text-xs leading-5">{test}</code>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted-foreground">
                No automated tests were mapped.
              </p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <ListChecks className="size-4 text-primary" aria-hidden="true" />
              <CardTitle>Manual test plan</CardTitle>
            </div>
            <CardDescription>
              Generated exploratory and verification cases.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {impact.suggested_manual_tests.length ? (
              impact.suggested_manual_tests.map((test, index) => (
                <article key={`${test.title ?? "manual"}-${index}`} className="rounded-lg border p-4">
                  <div className="flex items-start justify-between gap-3">
                    <h3 className="text-sm font-semibold">
                      {test.title ?? `Manual test ${index + 1}`}
                    </h3>
                    {test.priority ? <StatusBadge value={test.priority} /> : null}
                  </div>
                  {test.preconditions?.length ? (
                    <div className="mt-3">
                      <p className="text-xs font-semibold text-muted-foreground">
                        Preconditions
                      </p>
                      <ul className="mt-1 list-inside list-disc text-xs leading-5 text-muted-foreground">
                        {test.preconditions.map((item, itemIndex) => (
                          <li key={`${item}-${itemIndex}`}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                  {test.steps?.length ? (
                    <div className="mt-3">
                      <p className="text-xs font-semibold text-muted-foreground">
                        Steps
                      </p>
                      <ol className="mt-1 list-inside list-decimal text-xs leading-5 text-muted-foreground">
                        {test.steps.map((step, stepIndex) => (
                          <li key={`${step}-${stepIndex}`}>{step}</li>
                        ))}
                      </ol>
                    </div>
                  ) : null}
                  {test.expected_result ? (
                    <p className="mt-3 rounded-md bg-muted/50 p-2 text-xs leading-5">
                      <span className="font-semibold">Expected: </span>
                      {test.expected_result}
                    </p>
                  ) : null}
                </article>
              ))
            ) : (
              <p className="text-sm text-muted-foreground">
                No manual test cases were generated.
              </p>
            )}
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
