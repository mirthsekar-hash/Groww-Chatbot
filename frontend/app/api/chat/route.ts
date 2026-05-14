import { NextRequest, NextResponse } from "next/server";
import { getBackendBaseUrl } from "@/lib/backendBaseUrl";

export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  const base = getBackendBaseUrl();
  const body = await req.text();
  const contentType =
    req.headers.get("content-type") || "application/json";

  try {
    const res = await fetch(`${base}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": contentType, Accept: "application/json" },
      body,
      cache: "no-store",
    });
    const text = await res.text();
    return new NextResponse(text, {
      status: res.status,
      headers: {
        "Content-Type": res.headers.get("content-type") || "application/json",
      },
    });
  } catch {
    return NextResponse.json(
      { reply: "Could not reach the API server. Start the backend on port 8000 (see README)." },
      { status: 502 },
    );
  }
}
