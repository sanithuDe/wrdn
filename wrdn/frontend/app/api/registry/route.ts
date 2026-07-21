import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const BACKEND_URL =
  process.env.INTERNAL_API_URL ||
  "http://backend:8000";

export async function GET() {
  try {
    const response = await fetch(
      `${BACKEND_URL}/api/registry`,
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