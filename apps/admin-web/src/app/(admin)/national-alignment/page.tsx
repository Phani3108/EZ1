/**
 * National Alignment page — Zimbabwe national identity and educational alignment.
 * Ministry-safe, no political figures. Shows flag, coat of arms, motto,
 * national anthem, and alignment with Vision 2030.
 */

"use client";

import React from "react";
import { useTranslations } from "next-intl";
import { Card, CardContent } from "@eduzim/ui";
import { Shield, BookOpen, Target, Star } from "lucide-react";

/** Zimbabwe flag rendered as SVG */
function ZimFlag() {
  return (
    <svg
      viewBox="0 0 360 180"
      className="w-full max-w-xs rounded shadow-sm border"
      role="img"
      aria-label="Flag of Zimbabwe"
    >
      {/* 7 horizontal bands */}
      <rect y="0" width="360" height="25.7" fill="#008751" />
      <rect y="25.7" width="360" height="25.7" fill="#FFD200" />
      <rect y="51.4" width="360" height="25.7" fill="#D62828" />
      <rect y="77.1" width="360" height="25.7" fill="#1A1A1A" />
      <rect y="102.8" width="360" height="25.7" fill="#D62828" />
      <rect y="128.5" width="360" height="25.7" fill="#FFD200" />
      <rect y="154.2" width="360" height="25.7" fill="#008751" />
      {/* White triangle */}
      <polygon points="0,0 120,90 0,180" fill="#FFFFFF" />
      {/* Zimbabwe Bird on soapstone + red star */}
      <g transform="translate(36, 55)">
        <polygon
          points="25,0 31,18 50,18 35,29 41,47 25,37 9,47 15,29 0,18 19,18"
          fill="#D62828"
          transform="scale(1.2) translate(2, -8)"
        />
        {/* Simplified bird silhouette */}
        <text
          x="30"
          y="50"
          fontSize="24"
          fontWeight="bold"
          fill="#1A1A1A"
          textAnchor="middle"
          fontFamily="serif"
        >
          🦅
        </text>
      </g>
    </svg>
  );
}

/** Zimbabwe flag stripe */
function ZimStripe() {
  return (
    <div className="flex h-2 w-full overflow-hidden rounded-full" aria-hidden="true">
      <div className="flex-1 bg-[#008751]" />
      <div className="flex-1 bg-[#FFD200]" />
      <div className="flex-1 bg-[#D62828]" />
      <div className="flex-1 bg-[#1A1A1A]" />
      <div className="flex-1 bg-[#D62828]" />
      <div className="flex-1 bg-[#FFD200]" />
      <div className="flex-1 bg-[#008751]" />
    </div>
  );
}

export default function NationalAlignmentPage() {
  const t = useTranslations("national");

  const values = [
    { icon: Star, key: "valueExcellence" as const },
    { icon: Shield, key: "valueTransparency" as const },
    { icon: BookOpen, key: "valueInclusion" as const },
    { icon: Target, key: "valueInnovation" as const },
  ];

  return (
    <div className="px-6 lg:px-8 py-6 space-y-8 max-w-4xl mx-auto">
      {/* Header */}
      <div className="text-center space-y-3">
        <h1 className="text-[28px] leading-[36px] font-bold tracking-tight">
          {t("title")}
        </h1>
        <p className="text-[15px] text-muted-foreground max-w-2xl mx-auto">
          {t("subtitle")}
        </p>
        <ZimStripe />
      </div>

      {/* Flag + Motto */}
      <div className="flex flex-col items-center gap-4">
        <ZimFlag />
        <p className="text-lg font-semibold text-foreground italic">
          &ldquo;{t("motto")}&rdquo;
        </p>
      </div>

      {/* Education for All */}
      <Card>
        <CardContent className="pt-6 space-y-3">
          <h2 className="text-[22px] leading-[28px] font-semibold tracking-tight">
            {t("educationTitle")}
          </h2>
          <p className="text-[14px] leading-[22px] text-muted-foreground">
            {t("educationBody")}
          </p>
        </CardContent>
      </Card>

      {/* Vision 2030 */}
      <Card>
        <CardContent className="pt-6 space-y-3">
          <h2 className="text-[22px] leading-[28px] font-semibold tracking-tight">
            {t("vision2030Title")}
          </h2>
          <p className="text-[14px] leading-[22px] text-muted-foreground">
            {t("vision2030Body")}
          </p>
        </CardContent>
      </Card>

      {/* National Anthem reference */}
      <Card>
        <CardContent className="pt-6 text-center space-y-2">
          <h2 className="text-[18px] font-semibold">{t("anthem")}</h2>
          <p className="text-[15px] text-muted-foreground italic">
            {t("anthemTitle")}
          </p>
        </CardContent>
      </Card>

      {/* Values */}
      <div className="space-y-4">
        <h2 className="text-[22px] leading-[28px] font-semibold tracking-tight text-center">
          {t("valuesTitle")}
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {values.map(({ icon: Icon, key }) => (
            <Card key={key}>
              <CardContent className="pt-6 flex items-center gap-3">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                  <Icon className="h-5 w-5 text-primary" />
                </div>
                <p className="text-[14px] font-medium">{t(key)}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      {/* Bottom stripe */}
      <ZimStripe />
    </div>
  );
}
