"use client";

import { useCallback, useRef } from "react";
import Image from "next/image";

const JSON_CONFIG = `{
  "mcpServers": {
    "sarvam": {
      "command": "uvx",
      "args": ["sarvam-mcp"],
      "env": {
        "SARVAM_API_KEY": "your_api_key_here"
      }
    }
  }
}`;

export default function Home() {
  const iconRef = useRef<SVGSVGElement>(null);

  const copyJson = useCallback(() => {
    navigator.clipboard.writeText(JSON_CONFIG);
    const icon = iconRef.current;
    if (!icon) return;

    icon.innerHTML =
      '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>';
    icon.style.color = "#16a34a";

    setTimeout(() => {
      icon.innerHTML =
        '<rect x="9" y="9" width="13" height="13" rx="2" ry="2" stroke-width="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" stroke-width="2"/>';
      icon.style.color = "";
    }, 1500);
  }, []);

  return (
    <div className="card">
      <Image
        src="/sarvam-logo.png"
        alt="Sarvam"
        width={120}
        height={32}
        className="logo"
        priority
      />

      <p>
        Paste this JSON into your favorite agent (Cursor, Claude Desktop,
        Windsurf, etc.) and it&apos;ll set up Sarvam for you.
      </p>

      <div className="cmd" onClick={copyJson}>
        <code>{JSON_CONFIG}</code>
        <svg
          ref={iconRef}
          className="copy-icon"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <rect
            x="9"
            y="9"
            width="13"
            height="13"
            rx="2"
            ry="2"
            strokeWidth="2"
          />
          <path
            d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"
            strokeWidth="2"
          />
        </svg>
      </div>

      <p className="note">
        API key optional upfront — the server will ask for it on first use.
        <br />
        Or grab one now from{" "}
        <a
          href="https://dashboard.sarvam.ai/key-management"
          target="_blank"
          rel="noopener noreferrer"
        >
          dashboard.sarvam.ai/key-management
        </a>
      </p>

      <div className="links">
        <a
          href="https://github.com/sarvamai/sarvam-mcp"
          target="_blank"
          rel="noopener noreferrer"
        >
          GitHub
        </a>
        <a
          href="https://docs.sarvam.ai"
          target="_blank"
          rel="noopener noreferrer"
        >
          Docs
        </a>
        <a
          href="https://dashboard.sarvam.ai/key-management"
          target="_blank"
          rel="noopener noreferrer"
        >
          Get API Key
        </a>
      </div>
    </div>
  );
}
