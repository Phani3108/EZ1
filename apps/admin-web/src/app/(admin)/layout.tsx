/**
 * Admin app shell layout — sidebar + main content + footer.
 * All /dashboard/* routes are wrapped in this layout.
 */

"use client";

import React from "react";
import { useRouter } from "next/navigation";
import { RouteGuard } from "@eduzim/auth";
import { Sidebar } from "@/components/sidebar";
import { Footer } from "@/components/footer";

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();

  return (
    <RouteGuard onUnauthenticated={() => router.replace("/login")}>
      <div className="flex min-h-screen">
        <Sidebar />
        <div className="flex flex-1 flex-col lg:ml-64 min-h-screen">
          <main className="flex-1 px-6 lg:px-8 py-6">{children}</main>
          <Footer />
        </div>
      </div>
    </RouteGuard>
  );
}
