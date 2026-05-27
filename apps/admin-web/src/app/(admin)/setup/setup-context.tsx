"use client";

import React from "react";
import type { OnboardingStatus } from "@/lib/onboarding-api";

export const SetupContext = React.createContext<{
  status: OnboardingStatus | null;
  refresh: () => void;
}>({ status: null, refresh: () => {} });

export function useSetup() {
  return React.useContext(SetupContext);
}
