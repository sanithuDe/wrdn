"use client";

import { fetchRegistryData } from "@/lib/registryApi";
import {
    useCallback,
    useEffect,
    useState,
} from "react";

export function useRegistryData() {
  const [registryData, setRegistryData] =
    useState<any>(null);

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

        setRegistryData(data);
        setLastUpdated(new Date());
        setError("");
      } catch (err) {
        console.error(
          "Registry fetch error:",
          err,
        );

        setError(
          err instanceof Error
            ? err.message
            : "Failed to load WRDN registry data",
        );
      } finally {
        setLoading(false);
      }
    }, []);

  useEffect(() => {
    loadRegistryData();

    const intervalId = setInterval(
      loadRegistryData,
      3000,
    );

    return () =>
      clearInterval(intervalId);
  }, [loadRegistryData]);

  return {
    registryData,
    loading,
    error,
    lastUpdated,
    refresh: loadRegistryData,
  };
}