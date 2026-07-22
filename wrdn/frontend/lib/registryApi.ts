export async function fetchRegistryData() {
  const response = await fetch(
    "/api/registry",
    {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
      cache: "no-store",
    },
  );

  const data = await response
    .json()
    .catch(() => null);

  if (!response.ok) {
    throw new Error(
      data?.error ||
        `Registry request failed: ${response.status}`,
    );
  }

  return data;
}