const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export async function fetchRegistryData() {
  const response = await fetch(`${API_BASE_URL}/api/registry`, {
    method: "GET",
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error("Failed to fetch WRDN registry data");
  }

  return response.json();
}