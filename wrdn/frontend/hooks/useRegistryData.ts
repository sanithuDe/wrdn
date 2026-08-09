"use client";

import { fetchRegistryData } from "@/lib/registryApi";
import {
    useCallback,
    useEffect,
    useState,
} from "react";

export interface RegistryLog {
  id: number;
  timestamp: string;
  username?: string;
  client_id?: string;
  user_prompt: string;
  raw_ai_output: string;
  shield_status: string;
  risk_score: number;
  detection_reason: string;
}

export interface RegistryResponse {
  company_name: string;
  database_status: string;
  database_type?: string;
  database_path?: string;
  employee_count?: number;
  audit_count?: number;
  allowed_count?: number;
  blocked_count?: number;
  scope?: string;
  viewer_role?: string;
  viewer_username?: string;
  client_id?: string;
  allowed_logs: RegistryLog[];
  blocked_logs: RegistryLog[];
  error?: string;
}

export function useRegistryData() {
  const [registryData, setRegistryData] =
    useState<RegistryResponse | null>(null);

  const [loading, setLoading] =
    useState(true);

  const [error, setError] =
    useState("");

  const [lastUpdated, setLastUpdated] =
    useState<Date | null>(null);

  const loadRegistryData =
    useCallback(async () => {
      try {
        const data =
          await fetchRegistryData();

        if (
          data.database_status === "ERROR"
        ) {
          throw new Error(
            data.error ||
              "The local SQLite database could not be read.",
          );
        }

        setRegistryData(data);
        setLastUpdated(new Date());
        setError("");
      } catch (requestError) {
        console.error(
          "Registry fetch error:",
          requestError,
        );

        setError(
          requestError instanceof Error
            ? requestError.message
            : "Failed to load WRDN registry data",
        );
      } finally {
        setLoading(false);
      }
    }, []);

  useEffect(() => {
    loadRegistryData();

    const intervalId =
      window.setInterval(
        loadRegistryData,
        3000,
      );

    return () =>
      window.clearInterval(intervalId);
  }, [loadRegistryData]);

  return {
    registryData,
    loading,
    error,
    lastUpdated,
    refresh: loadRegistryData,
  };
}