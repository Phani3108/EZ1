/**
 * Teacher Login Page
 * Credentials: teacher@eduzim.com / 123456
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

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "teacher@eduzim.com", password: "123456" },
  });

  const onSubmit = async (values: LoginForm) => {
    setServerError(null);
    try {
      const { data } = await auth.login({ email: values.email, password: values.password });
      await login(data);
      router.replace("/today");
    } catch {
      setServerError("Invalid email or password. Please try again.");
    }
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
            <h1 className="text-2xl font-bold text-gray-900">EduZim Teacher Portal</h1>
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
                  placeholder="teacher@eduzim.com"
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
                disabled={isSubmitting}
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

            <div className="mt-6 rounded-lg bg-blue-50 px-4 py-3 text-xs text-blue-700">
              <p className="font-semibold mb-1">Demo credentials</p>
              <p>Email: <span className="font-mono">teacher@eduzim.com</span></p>
              <p>Password: <span className="font-mono">123456</span></p>
            </div>
          </div>

          <p className="mt-6 text-center text-xs text-gray-400">
            Ministry of Primary and Secondary Education — Republic of Zimbabwe
          </p>
        </div>
      </div>

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
