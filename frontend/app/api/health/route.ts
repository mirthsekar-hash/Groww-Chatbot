import { NextResponse } from "next/server";
import { getBackendBaseUrl } from "@/lib/backendBaseUrl";

export const dynamic = "force-dynamic";

export async function GET() {
  const base = getBackendBaseUrl();
  try {
    const res = await fetch(`${base}/api/health`, {
      cache: "no-store",
      headers: { Accept: "application/json" },
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
      { status: "error", detail: "Backend unreachable" },
      { status: 502 },
    );
  }
}
