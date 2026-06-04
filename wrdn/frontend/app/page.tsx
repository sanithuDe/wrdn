"use client";

import { useState } from "react";

export default function Home() {
  const [prompt, setPrompt] = useState("");
  const [output, setOutput] = useState("");
  const [safe, setSafe] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(false);

  async function sendPrompt() {
    setLoading(true);
    setOutput("");

    try {
      const res = await fetch("http://127.0.0.1:8000/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ prompt }),
      });

      const data = await res.json();
      setOutput(data.final_output);
      setSafe(data.safe);
    } catch {
      setOutput("Error: Backend is not running.");
      setSafe(false);
    }

    setLoading(false);
  }

  return (
    <main className="min-h-screen bg-gray-100 p-10 text-black">
      <div className="max-w-3xl mx-auto bg-white p-6 rounded-xl shadow text-black">
        <h1 className="text-3xl font-bold mb-4 text-black">
          WRDN Output Sanitizer
        </h1>

        <textarea
          className="w-full border border-gray-400 p-3 rounded h-32 text-black bg-white placeholder-gray-500"
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

        {output && (
          <div className="mt-6 border border-gray-400 p-4 rounded bg-white text-black">
            <p className="text-black">
              <b>Status:</b> {safe ? "Safe Output" : "Sanitized / Error"}
            </p>

            <p className="mt-4 text-black">
              <b>Final Output:</b>
            </p>

            <p className="mt-2 whitespace-pre-wrap text-black">{output}</p>
          </div>
        )}
      </div>
    </main>
  );
}