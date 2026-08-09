import { getAuthUser } from "@/lib/authApi";

export async function fetchRegistryData() {
  const user = getAuthUser();

  const params = new URLSearchParams();
  if (user?.client_id) {
    params.set("client_id", user.client_id);
  }
  if (user?.username) {
    params.set("username", user.username);
  }
  if (user?.role) {
    params.set("role", user.role);
  }

  const query = params.toString();

  const response = await fetch(
    `/api/registry${query ? `?${query}` : ""}`,
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
