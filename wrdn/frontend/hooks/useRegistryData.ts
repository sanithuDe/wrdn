"use client";

import { fetchRegistryData } from "@/lib/registryApi";
import { useEffect, useState } from "react";

export function useRegistryData() {
  const [registryData, setRegistryData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  async function loadRegistryData() {
    try {
      const data = await fetchRegistryData();

      setRegistryData(data);
      setLastUpdated(new Date());
      setError("");
    } catch (err) {
      console.error(err);
      setError("Failed to load WRDN registry data");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadRegistryData();

    const intervalId = setInterval(() => {
      loadRegistryData();
    }, 3000);

    return () => clearInterval(intervalId);
  }, []);

  return {
    registryData,
    loading,
    error,
    lastUpdated,
    refresh: loadRegistryData,
  };
}


