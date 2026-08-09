import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const BACKEND_URL =
  process.env.INTERNAL_API_URL ||
  "http://backend:8000";

export async function GET(request: NextRequest) {
  try {
    const incoming = request.nextUrl.searchParams;
    const params = new URLSearchParams();

    for (const key of [
      "client_id",
      "username",
      "role",
    ]) {
      const value = incoming.get(key);
      if (value) {
        params.set(key, value);
      }
    }

    const query = params.toString();

    const response = await fetch(
      `${BACKEND_URL}/api/registry${
        query ? `?${query}` : ""
      }`,
      {
        cache: "no-store",
      },
    );

    const data = await response.json();

    return NextResponse.json(data, {
      status: response.status,
    });
  } catch (error) {
    return NextResponse.json(
      {
        error:
          error instanceof Error
            ? error.message
            : "Backend connection failed",
      },
      {
        status: 503,
      },
    );
  }
}
