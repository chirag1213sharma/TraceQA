"use client";

import {
  CheckCircle2,
  FolderOpen,
  GitBranch,
  KeyRound,
  LoaderCircle,
  Save,
  ShieldCheck,
  Sparkles,
  Trash2,
} from "lucide-react";
import { FormEvent, useState } from "react";
import useSWR from "swr";

import { ErrorState, LoadingState } from "@/components/data-state";
import { PageIntro } from "@/components/page-intro";
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  getRuntimeSettings,
  RuntimeSettings,
  RuntimeSettingsUpdate,
  updateRuntimeSettings,
} from "@/lib/api";

export default function SettingsPage() {
  const { data, error, isLoading, mutate } = useSWR<RuntimeSettings>(
    "traceqa-settings",
    getRuntimeSettings,
  );

  return (
    <div className="space-y-8">
      <PageIntro
        eyebrow="Workspace"
        title="Settings"
        description="Manage ingestion paths, source control access, and model provider credentials without exposing stored secrets."
      />

      {isLoading ? <LoadingState label="Loading workspace settings" /> : null}
      {error ? (
        <ErrorState
          error={error instanceof Error ? error : new Error("Unknown API error")}
          onRetry={() => mutate()}
        />
      ) : null}
      {data && !error ? (
        <SettingsForm
          key={`${data.test_logs_directory}-${data.llm_model}-${data.llm_api_base}-${data.llm_api_key_configured}-${data.github_token_configured}-${data.github_webhook_secret_configured}`}
          settings={data}
          onSaved={(updated) => mutate(updated, false)}
        />
      ) : null}
    </div>
  );
}

function SettingsForm({
  settings,
  onSaved,
}: {
  settings: RuntimeSettings;
  onSaved: (settings: RuntimeSettings) => void;
}) {
  const [directory, setDirectory] = useState(settings.test_logs_directory);
  const [model, setModel] = useState(settings.llm_model);
  const [apiBase, setApiBase] = useState(settings.llm_api_base);
  const [llmApiKey, setLlmApiKey] = useState("");
  const [githubToken, setGithubToken] = useState("");
  const [webhookSecret, setWebhookSecret] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState<{
    tone: "success" | "error";
    text: string;
  } | null>(null);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSaving(true);
    setMessage(null);
    const payload: RuntimeSettingsUpdate = {
      test_logs_directory: directory.trim(),
      llm_model: model.trim(),
      llm_api_base: apiBase.trim(),
    };
    if (llmApiKey) payload.llm_api_key = llmApiKey;
    if (githubToken) payload.github_token = githubToken;
    if (webhookSecret) payload.github_webhook_secret = webhookSecret;

    try {
      const updated = await updateRuntimeSettings(payload);
      setLlmApiKey("");
      setGithubToken("");
      setWebhookSecret("");
      onSaved(updated);
      setMessage({
        tone: "success",
        text: "Workspace settings were updated successfully.",
      });
    } catch (requestError) {
      setMessage({
        tone: "error",
        text:
          requestError instanceof Error
            ? requestError.message
            : "Settings could not be updated.",
      });
    } finally {
      setIsSaving(false);
    }
  }

  async function clearCredential(
    field:
      | "llm_api_key"
      | "github_token"
      | "github_webhook_secret",
  ) {
    setIsSaving(true);
    setMessage(null);
    try {
      const updated = await updateRuntimeSettings({ [field]: "" });
      onSaved(updated);
      setMessage({
        tone: "success",
        text: "The stored credential was removed.",
      });
    } catch (requestError) {
      setMessage({
        tone: "error",
        text:
          requestError instanceof Error
            ? requestError.message
            : "The credential could not be removed.",
      });
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <form onSubmit={save} className="space-y-5">
      {message ? (
        <Alert variant={message.tone === "error" ? "destructive" : "default"}>
          {message.tone === "success" ? (
            <CheckCircle2 aria-hidden="true" />
          ) : (
            <ShieldCheck aria-hidden="true" />
          )}
          <AlertTitle>
            {message.tone === "success" ? "Settings saved" : "Update failed"}
          </AlertTitle>
          <AlertDescription>{message.text}</AlertDescription>
        </Alert>
      ) : null}

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <FolderOpen className="size-4 text-primary" aria-hidden="true" />
            <CardTitle>Test ingestion</CardTitle>
          </div>
          <CardDescription>
            Local Google Drive sync directory scanned when ingestion runs.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            <Label htmlFor="directory">Test log directory</Label>
            <Input
              id="directory"
              value={directory}
              onChange={(event) => setDirectory(event.target.value)}
              placeholder="C:\TraceQA\test-logs"
              required
            />
            <p className="text-xs text-muted-foreground">
              The path is resolved by the machine running the FastAPI service.
            </p>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Sparkles className="size-4 text-primary" aria-hidden="true" />
            <CardTitle>AI provider</CardTitle>
          </div>
          <CardDescription>
            TraceQA uses Google Gemini Cloud through LiteLLM structured outputs.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-5 lg:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="model">LiteLLM model</Label>
            <Input
              id="model"
              value={model}
              onChange={(event) => setModel(event.target.value)}
              placeholder="gemini/gemini-2.5-flash"
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="api-base">Gemini API endpoint</Label>
            <Input
              id="api-base"
              type="url"
              value={apiBase}
              onChange={(event) => setApiBase(event.target.value)}
              placeholder="https://generativelanguage.googleapis.com/v1beta"
              required
            />
          </div>
          <CredentialField
            id="llm-key"
            label="Gemini API key"
            value={llmApiKey}
            onChange={setLlmApiKey}
            configured={settings.llm_api_key_configured}
            disabled={isSaving}
            onClear={() => clearCredential("llm_api_key")}
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <GitBranch className="size-4 text-primary" aria-hidden="true" />
            <CardTitle>GitHub integration</CardTitle>
          </div>
          <CardDescription>
            Credentials used to verify push events and retrieve private commit diffs.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-5 lg:grid-cols-2">
          <CredentialField
            id="github-token"
            label="Personal access token"
            value={githubToken}
            onChange={setGithubToken}
            configured={settings.github_token_configured}
            disabled={isSaving}
            onClear={() => clearCredential("github_token")}
          />
          <CredentialField
            id="webhook-secret"
            label="Webhook secret"
            value={webhookSecret}
            onChange={setWebhookSecret}
            configured={settings.github_webhook_secret_configured}
            disabled={isSaving}
            onClear={() => clearCredential("github_webhook_secret")}
          />
          <div className="rounded-lg border bg-muted/30 p-3 lg:col-span-2">
            <p className="text-xs font-medium">GitHub webhook endpoint</p>
            <code className="mt-1 block break-all text-xs text-muted-foreground">
              http://localhost:8000/api/v1/github/webhooks/push
            </code>
          </div>
        </CardContent>
      </Card>

      <div className="flex justify-end">
        <Button type="submit" disabled={isSaving}>
          {isSaving ? (
            <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />
          ) : (
            <Save className="size-4" aria-hidden="true" />
          )}
          Save settings
        </Button>
      </div>
    </form>
  );
}

function CredentialField({
  id,
  label,
  value,
  onChange,
  configured,
  disabled,
  onClear,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  configured: boolean;
  disabled: boolean;
  onClear: () => void;
}) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-3">
        <Label htmlFor={id}>{label}</Label>
        <Badge
          variant="outline"
          className={
            configured
              ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400"
              : "text-muted-foreground"
          }
        >
          <KeyRound className="size-3" aria-hidden="true" />
          {configured ? "Configured" : "Not configured"}
        </Badge>
      </div>
      <div className="flex gap-2">
        <Input
          id={id}
          type="password"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder={configured ? "Enter a replacement value" : "Enter credential"}
          autoComplete="new-password"
        />
        {configured ? (
          <Button
            type="button"
            variant="outline"
            size="icon"
            aria-label={`Clear ${label}`}
            onClick={onClear}
            disabled={disabled}
          >
            <Trash2 className="size-4" aria-hidden="true" />
          </Button>
        ) : null}
      </div>
      <p className="text-xs text-muted-foreground">
        Stored values are masked and are never returned by the API.
      </p>
    </div>
  );
}
