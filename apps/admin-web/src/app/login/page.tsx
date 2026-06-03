/**
 * Admin Login Page
 * Credentials: admin@school.ac.zw / secureP@ss1 (seeded by scripts/dev-seed.sh)
 */

"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useAuth } from "@eduzim/auth";
import { auth } from "@/lib/api";

const loginSchema = z.object({
  email: z.string().email("Enter a valid email address"),
  password: z.string().min(1, "Password is required"),
});
type LoginForm = z.infer<typeof loginSchema>;

// Pre-production: allow exploration without credentials.
const GUEST_USER = {
  id: "guest-admin",
  email: "guest-admin@eduzim.com",
  full_name: "Guest Admin",
  school_id: "school-1",
  is_active: true,
  roles: ["admin"],
  permissions: ["*"],
  preferences: {
    language: "en" as const,
    theme_pref: "sovereign" as const,
    text_size: "md" as const,
    high_contrast: false,
    read_aloud_enabled: false,
    reduced_motion: false,
  },
};

export default function LoginPage() {
  const router = useRouter();
  const { login, loginAsGuest } = useAuth();
  const [serverError, setServerError] = useState<string | null>(null);
  const [guestSubmitting, setGuestSubmitting] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "admin@school.ac.zw", password: "secureP@ss1" },
  });

  const onSubmit = async (values: LoginForm) => {
    setServerError(null);
    try {
      const { data } = await auth.login({ email: values.email, password: values.password });
      await login(data);
      router.replace("/dashboard");
    } catch {
      setServerError("Invalid email or password. Please try again.");
    }
  };

  const onContinueAsGuest = () => {
    setServerError(null);
    setGuestSubmitting(true);
    // No API call — pure client-side hydration so this works even when the
    // backend is unreachable.
    loginAsGuest(GUEST_USER);
    router.replace("/dashboard");
  };

  return (
    <div className="min-h-screen flex flex-col bg-gray-50">
      {/* Zimbabwe flag accent bar */}
      <div className="h-1.5 w-full flex">
        <div className="flex-1 bg-[#006400]" />
        <div className="flex-1 bg-[#FFD200]" />
        <div className="flex-1 bg-[#D21034]" />
        <div className="flex-1 bg-black" />
        <div className="flex-1 bg-[#FFD200]" />
        <div className="flex-1 bg-[#006400]" />
      </div>

      <div className="flex flex-1 items-center justify-center px-4 py-12">
        <div className="w-full max-w-md">
          {/* Logo */}
          <div className="mb-8 text-center">
            <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-primary text-2xl font-bold text-primary-foreground shadow">
              E
            </div>
            <h1 className="text-2xl font-bold text-gray-900">EduZim Admin Portal</h1>
            <p className="mt-1 text-sm text-gray-500">
              Harare Central Secondary School
            </p>
          </div>

          {/* Card */}
          <div className="rounded-2xl bg-white px-8 py-8 shadow-lg ring-1 ring-gray-200">
            <h2 className="mb-6 text-lg font-semibold text-gray-800">Sign in to your account</h2>

            {serverError && (
              <div className="mb-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700 ring-1 ring-red-200">
                {serverError}
              </div>
            )}

            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
              <div>
                <label className="mb-1.5 block text-sm font-medium text-gray-700">
                  Email address
                </label>
                <input
                  {...register("email")}
                  type="email"
                  autoComplete="email"
                  className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 placeholder-gray-400 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                  placeholder="admin@school.ac.zw"
                />
                {errors.email && (
                  <p className="mt-1 text-xs text-red-600">{errors.email.message}</p>
                )}
              </div>

              <div>
                <label className="mb-1.5 block text-sm font-medium text-gray-700">
                  Password
                </label>
                <input
                  {...register("password")}
                  type="password"
                  autoComplete="current-password"
                  className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 placeholder-gray-400 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                  placeholder="••••••"
                />
                {errors.password && (
                  <p className="mt-1 text-xs text-red-600">{errors.password.message}</p>
                )}
              </div>

              <button
                type="submit"
                disabled={isSubmitting || guestSubmitting}
                className="mt-2 flex w-full items-center justify-center rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground shadow hover:bg-primary/90 disabled:opacity-60"
              >
                {isSubmitting ? (
                  <span className="flex items-center gap-2">
                    <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                    Signing in…
                  </span>
                ) : (
                  "Sign in"
                )}
              </button>
            </form>

            {/* Guest access — pre-production */}
            <div className="mt-5">
              <div className="relative mb-4">
                <div className="absolute inset-0 flex items-center" aria-hidden="true">
                  <div className="w-full border-t border-gray-200" />
                </div>
                <div className="relative flex justify-center">
                  <span className="bg-white px-2 text-xs uppercase tracking-wider text-gray-400">or</span>
                </div>
              </div>
              <button
                type="button"
                onClick={onContinueAsGuest}
                disabled={isSubmitting || guestSubmitting}
                className="flex w-full items-center justify-center rounded-lg border border-gray-300 bg-white px-4 py-2.5 text-sm font-semibold text-gray-700 shadow-sm hover:bg-gray-50 disabled:opacity-60"
              >
                {guestSubmitting ? (
                  <span className="flex items-center gap-2">
                    <span className="h-4 w-4 animate-spin rounded-full border-2 border-gray-400 border-t-transparent" />
                    Starting guest session…
                  </span>
                ) : (
                  "Continue as Guest"
                )}
              </button>
              <p className="mt-2 text-center text-[11px] text-gray-400">
                Preview build — sign-in is not yet required.
              </p>
            </div>

            {/* Demo credentials hint */}
            <div className="mt-6 rounded-lg bg-blue-50 px-4 py-3 text-xs text-blue-700">
              <p className="font-semibold mb-1">Demo credentials</p>
              <p>Admin: <span className="font-mono">admin@school.ac.zw</span> / <span className="font-mono">secureP@ss1</span></p>
              <p>Teacher: <span className="font-mono">teacher@eduzim.zw</span> / <span className="font-mono">teacher123</span></p>
              <p>Parent: <span className="font-mono">parent@school.ac.zw</span> / <span className="font-mono">secureP@ss1</span></p>
            </div>
          </div>

          {/* Footer */}
          <p className="mt-6 text-center text-xs text-gray-400">
            Ministry of Primary and Secondary Education — Republic of Zimbabwe
          </p>
        </div>
      </div>

      {/* Bottom Zimbabwe flag stripe */}
      <div className="h-1.5 w-full flex">
        <div className="flex-1 bg-[#006400]" />
        <div className="flex-1 bg-[#FFD200]" />
        <div className="flex-1 bg-[#D21034]" />
        <div className="flex-1 bg-black" />
        <div className="flex-1 bg-[#FFD200]" />
        <div className="flex-1 bg-[#006400]" />
      </div>
    </div>
  );
}
