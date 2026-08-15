import type { ReactNode } from "react";

/**
 * Auth routes need page scroll. The app shell sets body overflow:hidden.
 */
export default function AuthLayout({
  children,
}: {
  children: ReactNode;
}) {
  return (
    <>
      <style>{`
        html,
        body {
          height: 100% !important;
          min-height: 100% !important;
          overflow: hidden !important;
        }

        @media (max-width: 900px) {
          html,
          body {
            overflow: auto !important;
            height: auto !important;
          }
        }
      `}</style>
      {children}
    </>
  );
}
