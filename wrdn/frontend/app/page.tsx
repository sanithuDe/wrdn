"use client";

import { useState } from "react";

type ChatResult = {
  user_prompt?: string;
  raw_ai_output?: string;
  shield_status?: string;
  risk_score?: number;
  detection_layer?: string;
  detection_reason?: string;
  final_output?: string;
  error?: string;
};

export default function Home() {
  const [prompt, setPrompt] = useState("");
  const [result, setResult] = useState<ChatResult | null>(null);
  const [loading, setLoading] = useState(false);

  async function sendPrompt() {
    setLoading(true);
    setResult(null);

    try {
      const res = await fetch("http://127.0.0.1:8000/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ prompt }),
      });

      const data = await res.json();
      setResult(data);
    } catch {
      setResult({
        shield_status: "ERROR",
        risk_score: 0,
        detection_reason: "Backend is not running.",
        final_output: "Error: Backend is not running.",
      });
    }

    setLoading(false);
  }

  return (
    <main className="min-h-screen bg-gray-100 p-10 text-black">
      <div className="max-w-3xl mx-auto bg-white p-6 rounded-xl shadow text-black">
        <h1 className="text-3xl font-bold mb-4">
          WRDN Output Sanitizer
        </h1>

        <textarea
          className="w-full border border-gray-400 p-3 rounded h-32 text-black bg-white"
          placeholder="Enter your prompt..."
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
        />

        <button
          onClick={sendPrompt}
          disabled={loading}
          className="mt-4 bg-black text-white px-5 py-2 rounded"
        >
          {loading ? "Checking..." : "Send"}
        </button>

        {result && (
          <div className="mt-6 border border-gray-400 p-4 rounded bg-white text-black">
            <p>
              <b>Status:</b> {result.shield_status}
            </p>

            <p>
              <b>Risk Score:</b> {result.risk_score}
            </p>

            <p>
              <b>Reason:</b> {result.detection_reason}
            </p>

            <p className="mt-6">
              <b>Final Output:</b>
            </p>

            <p className="mt-4 whitespace-pre-wrap">
              {result.final_output || result.error}
            </p>
          </div>
        )}
      </div>
    </main>
  );
}