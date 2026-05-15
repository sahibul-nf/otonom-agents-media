import {NextRequest, NextResponse} from "next/server";

const API_BASE = process.env.MEDIA_ENGINE_API_BASE || "http://127.0.0.1:8765";

type Params = {
  params: Promise<{path: string[]}>;
};

async function forward(request: NextRequest, {params}: Params) {
  const {path} = await params;
  const url = new URL(request.url);
  const upstream = new URL(`/api/${path.join("/")}${url.search}`, API_BASE);
  const body = request.method === "GET" || request.method === "HEAD" ? undefined : await request.text();
  let response: Response;
  try {
    response = await fetch(upstream, {
      method: request.method,
      headers: {
        "Content-Type": request.headers.get("Content-Type") || "application/json",
      },
      body,
      cache: "no-store",
    });
  } catch {
    return NextResponse.json(
      {error: `Media engine API is offline. Start it at ${API_BASE}.`},
      {status: 503},
    );
  }
  const contentType = response.headers.get("Content-Type") || "";
  if (contentType.includes("application/json")) {
    const text = await response.text();
    if (!text.trim()) {
      return NextResponse.json({error: `Media engine returned an empty response for /api/${path.join("/")}.`}, {status: response.status || 502});
    }
    return NextResponse.json(JSON.parse(text), {status: response.status});
  }
  return new NextResponse(await response.arrayBuffer(), {
    status: response.status,
    headers: {"Content-Type": contentType || "application/octet-stream"},
  });
}

export const GET = forward;
export const POST = forward;
