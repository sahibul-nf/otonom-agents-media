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
  const response = await fetch(upstream, {
    method: request.method,
    headers: {
      "Content-Type": request.headers.get("Content-Type") || "application/json",
    },
    body,
    cache: "no-store",
  });
  const contentType = response.headers.get("Content-Type") || "";
  if (contentType.includes("application/json")) {
    return NextResponse.json(await response.json(), {status: response.status});
  }
  return new NextResponse(await response.arrayBuffer(), {
    status: response.status,
    headers: {"Content-Type": contentType || "application/octet-stream"},
  });
}

export const GET = forward;
export const POST = forward;
