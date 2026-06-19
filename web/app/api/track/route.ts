import { NextResponse } from "next/server";
import { emitToolUsed, type ToolEvent } from "@/lib/signoz";

const REQUIRED_FIELDS: (keyof ToolEvent)[] = [
  "tool",
  "status",
  "version",
  "python",
  "os",
  "install_id",
];
// "arguments" and "response" are optional

export async function POST(request: Request) {
  try {
    const body = await request.json();

    const missing = REQUIRED_FIELDS.filter(
      (f) => typeof body[f] !== "string" || body[f] === "",
    );
    if (missing.length > 0) {
      return NextResponse.json(
        { error: `missing fields: ${missing.join(", ")}` },
        { status: 400 },
      );
    }

    emitToolUsed(body as ToolEvent);
  } catch {
    // Swallow all errors — tracking must never block callers.
  }

  return new NextResponse(null, { status: 204 });
}
