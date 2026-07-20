const API_URL =
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000";

export async function fetchRegistryData() {
  const response = await fetch(
    `${API_URL}/api/registry`,
    {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
      cache: "no-store",
    },
  );

  if (!response.ok) {
    throw new Error(
      `Registry API request failed: ${response.status}`,
    );
  }

  return response.json();
}