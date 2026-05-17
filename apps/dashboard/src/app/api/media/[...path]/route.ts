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
  const requestHeaders = new Headers();
  const requestContentType = request.headers.get("Content-Type");
  const range = request.headers.get("Range");
  if (requestContentType) requestHeaders.set("Content-Type", requestContentType);
  if (range) requestHeaders.set("Range", range);
  let response: Response;
  try {
    response = await fetch(upstream, {
      method: request.method,
      headers: requestHeaders,
      body,
      cache: "no-store",
    });
  } catch {
    return NextResponse.json(
      {error: `Media engine API is offline. Start it at ${API_BASE}.`},
      {status: 503},
    );
  }
  const responseContentType = response.headers.get("Content-Type") || "";
  if (responseContentType.includes("application/json")) {
    const text = await response.text();
    if (!text.trim()) {
      return NextResponse.json({error: `Media engine returned an empty response for /api/${path.join("/")}.`}, {status: response.status || 502});
    }
    try {
      return NextResponse.json(JSON.parse(text), {status: response.status});
    } catch {
      return NextResponse.json(
        {error: `Media engine returned invalid JSON for /api/${path.join("/")}.`, raw: text.slice(0, 500)},
        {status: response.status >= 400 ? response.status : 502},
      );
    }
  }
  const passthroughHeaders = new Headers();
  if (responseContentType) passthroughHeaders.set("Content-Type", responseContentType);
  for (const header of ["Accept-Ranges", "Content-Length", "Content-Range", "Content-Disposition"]) {
    const value = response.headers.get(header);
    if (value) passthroughHeaders.set(header, value);
  }
  return new NextResponse(await response.arrayBuffer(), {
    status: response.status,
    headers: passthroughHeaders,
  });
}

export const GET = forward;
export const POST = forward;
