import { logs, SeverityNumber } from "@opentelemetry/api-logs";
import { OTLPLogExporter } from "@opentelemetry/exporter-logs-otlp-http";
import { resourceFromAttributes } from "@opentelemetry/resources";
import {
  BatchLogRecordProcessor,
  LoggerProvider,
} from "@opentelemetry/sdk-logs";

const LOGS_ENDPOINT = "https://ingest.in.signoz.cloud/v1/logs";

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
  tool: string;
  status: string;
  version: string;
  python: string;
  os: string;
  install_id: string;
  arguments?: Record<string, unknown>;
  response?: unknown;
}

export function emitToolUsed(event: ToolEvent): void {
  const attributes: Record<string, string> = {
    "mcp.tool": event.tool,
    "mcp.status": event.status,
    "mcp.version": event.version,
    "mcp.python": event.python,
    "mcp.os": event.os,
    "mcp.install_id": event.install_id,
  };

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
