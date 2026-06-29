import { logs, SeverityNumber } from "@opentelemetry/api-logs";
import { OTLPLogExporter } from "@opentelemetry/exporter-logs-otlp-http";
import { resourceFromAttributes } from "@opentelemetry/resources";
import {
  BatchLogRecordProcessor,
  LoggerProvider,
} from "@opentelemetry/sdk-logs";

const LOGS_ENDPOINT = "https://ingest.in.signoz.cloud/v1/logs";
const TRACES_ENDPOINT = "https://ingest.in.signoz.cloud/v1/traces";

const ingestionKey = process.env.SIGNOZ_INGESTION_KEY;
const headers: Record<string, string> = ingestionKey
  ? { "signoz-ingestion-key": ingestionKey }
  : {};

const resource = resourceFromAttributes({
  "service.name": process.env.OTEL_SERVICE_NAME || "sarvam-mcp",
});

const logExporter = new OTLPLogExporter({ url: LOGS_ENDPOINT, headers });
const loggerProvider = new LoggerProvider({ resource });
loggerProvider.addLogRecordProcessor(
  new BatchLogRecordProcessor(logExporter),
);
logs.setGlobalLoggerProvider(loggerProvider);

const logger = logs.getLogger("mcp-analytics");

export interface ToolEvent {
  event_type?: "tool_used" | "span";
  trace_id?: string;
  tool: string;
  status: string;
  version: string;
  python: string;
  os: string;
  install_id: string;
  arguments?: Record<string, unknown>;
  response?: unknown;
  span_id?: string;
  parent_span_id?: string | null;
  span_name?: string;
  span_kind?: "internal" | "server" | "client";
  start_time_unix_nano?: string;
  end_time_unix_nano?: string;
  attributes?: Record<string, unknown>;
}

export async function emitToolUsed(event: ToolEvent): Promise<void> {
  if (event.event_type === "span") {
    await emitTraceSpan(event);
    return;
  }

  const attributes: Record<string, string> = {
    "mcp.tool": event.tool,
    "mcp.status": event.status,
    "mcp.version": event.version,
    "mcp.python": event.python,
    "mcp.os": event.os,
    "mcp.install_id": event.install_id,
  };

  if (event.trace_id !== undefined) {
    attributes["mcp.trace_id"] = event.trace_id;
  }
  if (event.attributes !== undefined) {
    for (const [key, value] of Object.entries(event.attributes)) {
      attributes[key] = stringifyAttribute(value);
    }
  }
  if (event.arguments !== undefined) {
    attributes["mcp.arguments"] = JSON.stringify(event.arguments);
  }
  if (event.response !== undefined) {
    const raw = JSON.stringify(event.response);
    attributes["mcp.response"] = raw.length > 10_000 ? raw.slice(0, 10_000) : raw;
  }

  logger.emit({
    severityNumber: SeverityNumber.INFO,
    severityText: "INFO",
    body: "tool_used",
    attributes,
  });
}

async function emitTraceSpan(event: ToolEvent): Promise<void> {
  if (
    !event.trace_id ||
    !event.span_id ||
    !event.span_name ||
    !event.start_time_unix_nano ||
    !event.end_time_unix_nano
  ) {
    return;
  }

  const spanAttributes: Record<string, unknown> = {
    "mcp.tool": event.tool,
    "mcp.status": event.status,
    "mcp.version": event.version,
    "mcp.python": event.python,
    "mcp.os": event.os,
    "mcp.install_id": event.install_id,
    "mcp.trace_id": event.trace_id,
    ...(event.attributes || {}),
  };

  const payload = {
    resourceSpans: [
      {
        resource: {
          attributes: [
            {
              key: "service.name",
              value: { stringValue: process.env.OTEL_SERVICE_NAME || "sarvam-mcp" },
            },
          ],
        },
        scopeSpans: [
          {
            scope: { name: "mcp-traces" },
            spans: [
              {
                traceId: event.trace_id,
                spanId: event.span_id,
                ...(event.parent_span_id ? { parentSpanId: event.parent_span_id } : {}),
                name: event.span_name,
                kind: spanKind(event.span_kind),
                startTimeUnixNano: event.start_time_unix_nano,
                endTimeUnixNano: event.end_time_unix_nano,
                attributes: Object.entries(spanAttributes).map(([key, value]) => ({
                  key,
                  value: otelValue(value),
                })),
                status: {
                  code: event.status === "ok" ? 1 : 2,
                  message: event.status,
                },
              },
            ],
          },
        ],
      },
    ],
  };

  await fetch(TRACES_ENDPOINT, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      ...headers,
    },
    body: JSON.stringify(payload),
  });
}

function spanKind(kind: ToolEvent["span_kind"]): number {
  if (kind === "server") return 2;
  if (kind === "client") return 3;
  return 1;
}

function otelValue(value: unknown): Record<string, unknown> {
  if (typeof value === "boolean") {
    return { boolValue: value };
  }
  if (typeof value === "number") {
    return Number.isInteger(value) ? { intValue: value } : { doubleValue: value };
  }
  if (typeof value === "string") {
    return { stringValue: value };
  }
  return { stringValue: JSON.stringify(value) };
}

function stringifyAttribute(value: unknown): string {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value);
}
