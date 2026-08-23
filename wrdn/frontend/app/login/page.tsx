"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/**
 * Keep /login working for existing redirects.
 * Canonical entry is /signin.
 */
export default function LoginRedirectPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/signin");
  }, [router]);

  return (
    <main
      style={{
        minHeight: "100vh",
        display: "grid",
        placeItems: "center",
        background: "#05070c",
        color: "#9aa3b2",
        fontFamily: "Arial, Helvetica, sans-serif",
      }}
    >
      Redirecting to sign in…
    </main>
  );
}
