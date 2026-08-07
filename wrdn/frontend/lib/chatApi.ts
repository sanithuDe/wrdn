const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ||
  "http://localhost:18000";

export interface ChatApiResponse {
  user_prompt?: string;
  raw_ai_output?: string;
  final_output?: string;
  response?: string;
  answer?: string;
  shield_status?: string;
  risk_score?: number;
  detection_layer?: string;
  detection_reason?: string;
  client_id?: string;
  policy_id?: number;
  policy_version?: number;
  status?: string;
  error?: string;
}

export async function sendChatMessage(
  userPrompt: string,
  clientId: string,
): Promise<ChatApiResponse> {
  let response: Response;

  try {
    response = await fetch(`${API_URL}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        prompt: userPrompt,
        client_id: clientId,
      }),
    });
  } catch {
    throw new Error(
      `Cannot connect to WRDN backend at ${API_URL}. Confirm that FastAPI is running.`,
    );
  }

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(
      data?.detail?.[0]?.msg ||
        data?.detail ||
        data?.error ||
        `Chat request failed with status ${response.status}`,
    );
  }

  return data;
}