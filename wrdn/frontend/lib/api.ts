const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:18000"
).replace(/\/+$/, "");

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const isFormData =
    typeof FormData !== "undefined" &&
    options.body instanceof FormData;

  const headers = new Headers(options.headers);

  if (!isFormData && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(
    `${API_BASE_URL}${path}`,
    {
      ...options,
      headers,
    },
  );

  const responseText = await response.text();

  let data: unknown = null;

  if (responseText) {
    try {
      data = JSON.parse(responseText);
    } catch {
      data = responseText;
    }
  }

  if (!response.ok) {
    let errorMessage = "API request failed.";
  
    if (
      typeof data === "object" &&
      data !== null &&
      "detail" in data
    ) {
      const detail = (data as { detail: unknown }).detail;
  
      if (typeof detail === "string") {
        errorMessage = detail;
      } else if (Array.isArray(detail)) {
        errorMessage = detail
          .map((item) => {
            if (
              typeof item === "object" &&
              item !== null &&
              "msg" in item
            ) {
              return String(
                (item as { msg: unknown }).msg,
              );
            }
  
            return JSON.stringify(item);
          })
          .join(" | ");
      } else {
        errorMessage = JSON.stringify(detail);
      }
    } else if (typeof data === "string" && data) {
      errorMessage = data;
    }
  
    throw new Error(errorMessage);
  }
  

  if (response.status === 204) {
    return undefined as T;
  }

  return data as T;
}

export type CreateClientRequest = {
  client_id: string;
  client_name: string;
};

export type ClientResponse = {
  client_id: string;
  client_name: string;
  status: string;
};

export type ClientListItem = {
  ClientID: string;
  ClientName: string;
  CreatedAt: string;
};

export type RequirementUploadResponse = {
  requirement_id: number;
  client_id: string;
  filename: string;
  file_type: string;
  status: string;
  text_preview: string;
};

export type PolicyGenerationResponse = {
  policy_id: number;
  client_id: string;
  version: number;
  status: string;
  validation_errors: string[];
  policy: Record<string, unknown>;
};

export type PolicyValidationResponse = {
  policy_id: number;
  status: string;
  validation_errors: string[];
};

export type PolicyActivationResponse = {
  policy_id: number;
  client_id: string;
  status: string;
};

export type PolicyHistoryItem = {
  PolicyID: number;
  ClientID: string;
  RequirementFileID: number;
  PolicyName: string;
  Version: number;
  Status: string;
  ValidationErrors: string[];
  CreatedAt: string;
  ActivatedAt?: string | null;
  Policy?: {
    policy_name?: string;
    blocked_categories?: string[];
    sensitive_pattern_ids?: string[];
    allowed_secret_names?: string[];
    blocked_secret_names?: string[];
    allowed_employee_salary_names?: string[];
    blocked_employee_salary_names?: string[];
    allowed_actions?: string[];
    blocked_response?: string;
    explanation?: string;
    risk_threshold?: number;
    embedding_threshold?: number;
  };
};

export async function createClient(
  client: CreateClientRequest,
): Promise<ClientResponse> {
  return apiFetch<ClientResponse>(
    "/api/admin/clients",
    {
      method: "POST",
      body: JSON.stringify(client),
    },
  );
}

export async function listClients(): Promise<ClientListItem[]> {
  return apiFetch<ClientListItem[]>(
    "/api/admin/clients",
  );
}

export async function uploadRequirement(
  clientId: string,
  file: File,
): Promise<RequirementUploadResponse> {
  const formData = new FormData();

  formData.append("file", file);

  return apiFetch<RequirementUploadResponse>(
    `/api/admin/clients/${encodeURIComponent(
      clientId,
    )}/requirements`,
    {
      method: "POST",
      body: formData,
    },
  );
}

export async function analyzeRequirement(
  requirementId: number,
  clientId: string,
): Promise<PolicyGenerationResponse> {
  return apiFetch<PolicyGenerationResponse>(
    `/api/admin/requirements/${requirementId}/analyze?client_id=${encodeURIComponent(
      clientId.trim(),
    )}`,
    {
      method: "POST",
    },
  );
}

export async function validatePolicy(
  policyId: number,
  clientId: string,
): Promise<PolicyValidationResponse> {
  return apiFetch<PolicyValidationResponse>(
    `/api/admin/policies/${policyId}/validate`,
    {
      method: "POST",
      body: JSON.stringify({
        client_id: clientId,
      }),
    },
  );
}

export async function activatePolicy(
  policyId: number,
  clientId: string,
): Promise<PolicyActivationResponse> {
  return apiFetch<PolicyActivationResponse>(
    `/api/admin/policies/${policyId}/activate`,
    {
      method: "POST",
      body: JSON.stringify({
        client_id: clientId,
      }),
    },
  );
}

export async function listPolicies(
  clientId: string,
): Promise<PolicyHistoryItem[]> {
  const safeClientId = clientId.trim();

  return apiFetch<PolicyHistoryItem[]>(
    `/api/admin/policy-history?client_id=${encodeURIComponent(
      safeClientId,
    )}`,
  );
}

export async function listAllPolicies(): Promise<PolicyHistoryItem[]> {
  return apiFetch<PolicyHistoryItem[]>(
    "/api/admin/policy-history",
  );
}

export async function rollbackPolicy(
  policyId: number,
  clientId: string,
): Promise<PolicyActivationResponse> {
  return apiFetch<PolicyActivationResponse>(
    `/api/admin/policies/${policyId}/rollback`,
    {
      method: "POST",
      body: JSON.stringify({
        client_id: clientId,
      }),
    },
  );
}

export async function deletePolicy(
  policyId: number,
  clientId: string,
): Promise<{
  policy_id: number;
  client_id: string;
  status: string;
}> {
  return apiFetch(
    `/api/admin/policies/${policyId}`,
    {
      method: "DELETE",
      body: JSON.stringify({
        client_id: clientId,
      }),
    },
  );
}