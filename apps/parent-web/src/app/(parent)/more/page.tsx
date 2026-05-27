/**
 * "More" — Phase 12f parent-side lifestyle surfaces consolidated.
 *
 *   - Transport (P-012): live-ish bus status
 *   - Meal credit (P-013): per-child balance + topup
 *   - Donations (P-014): submit a donation
 *   - Newsletter (P-015): read-only school feed
 *   - Gallery (P-016): photo grid
 */

"use client";

import React, { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import {
  Card, CardContent, CardHeader, CardTitle, Button,
} from "@eduzim/ui";
import {
  Bus, UtensilsCrossed, HandCoins, Newspaper, Image as ImageIcon, Plus,
} from "lucide-react";
import { useChild } from "@/lib/child-context";
import { fetchJson, postJson } from "@/lib/api-helpers";


interface BusInfo {
  id: string;
  label: string;
  plate_number: string | null;
  route_description: string | null;
  latest_ping: {
    status: string;
    lat: number | null;
    lng: number | null;
    note: string | null;
    occurred_at: string;
  } | null;
}

interface NewsletterPost {
  id: string;
  title: string;
  body: string;
  published_at: string;
}

interface GalleryItem {
  id: string;
  attachment_id: string;
  caption: string | null;
  published_at: string;
}

interface DonationRow {
  id: string;
  amount_cents: number;
  currency: string;
  purpose: string | null;
  created_at: string;
}


export default function MorePage() {
  const t = useTranslations("parentMore");
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <h1 className="text-2xl font-bold tracking-tight">{t("title")}</h1>
      <p className="text-sm text-muted-foreground">{t("description")}</p>
      <TransportSection />
      <MealCreditSection />
      <DonationsSection />
      <NewsletterSection />
      <GallerySection />
    </div>
  );
}


// ─── Transport ─────────────────────────────────────────────────────


function TransportSection() {
  const t = useTranslations("parentMore");
  const [buses, setBuses] = useState<BusInfo[]>([]);

  useEffect(() => {
    (async () => {
      try {
        const r = await fetchJson<BusInfo[]>("/api/v1/transport-buses");
        setBuses(r.data);
      } catch {
        setBuses([]);
      }
    })();
  }, []);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Bus className="h-4 w-4" /> {t("transport.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {buses.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("transport.empty")}</p>
        ) : (
          <ul className="space-y-2">
            {buses.map((b) => (
              <li key={b.id} className="border rounded-md p-3 text-sm">
                <div className="flex items-center justify-between">
                  <span className="font-medium">{b.label}</span>
                  {b.latest_ping && (
                    <span
                      className={`text-xs rounded-full px-2 py-0.5 ${
                        b.latest_ping.status === "arrived"
                          ? "bg-green-100 text-green-700"
                          : b.latest_ping.status === "delayed"
                          ? "bg-red-100 text-red-700"
                          : "bg-blue-100 text-blue-700"
                      }`}
                    >
                      {b.latest_ping.status}
                    </span>
                  )}
                </div>
                {b.route_description && (
                  <p className="text-xs text-muted-foreground mt-1">
                    {b.route_description}
                  </p>
                )}
                {b.latest_ping && (
                  <p className="text-xs text-muted-foreground mt-1">
                    {new Date(b.latest_ping.occurred_at).toLocaleString()}
                    {b.latest_ping.note ? ` — ${b.latest_ping.note}` : ""}
                  </p>
                )}
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}


// ─── Meal credit ───────────────────────────────────────────────────


function MealCreditSection() {
  const t = useTranslations("parentMore");
  const { selected } = useChild();
  const [balance, setBalance] = useState<number | null>(null);
  const [amountCents, setAmountCents] = useState("500");
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    if (!selected) return;
    (async () => {
      try {
        const r = await fetchJson<{ balance_cents: number }>(
          `/api/v1/meal-credit/${selected.id}`,
        );
        setBalance(r.data.balance_cents);
      } catch {
        setBalance(0);
      }
    })();
  }, [selected, refresh]);

  const topup = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selected) return;
    const r = await postJson("/api/v1/meal-credit/topup", {
      student_id: selected.id,
      amount_cents: Number(amountCents),
    });
    if (r.ok) setRefresh((n) => n + 1);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <UtensilsCrossed className="h-4 w-4" /> {t("meal.title")}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {!selected ? (
          <p className="text-sm text-muted-foreground">
            {t("meal.pickChild")}
          </p>
        ) : (
          <>
            <p className="text-sm">
              {t("meal.balance", {
                amount:
                  balance == null
                    ? "…"
                    : (balance / 100).toFixed(2),
              })}
            </p>
            <form onSubmit={topup} className="flex items-center gap-2">
              <input
                type="number"
                min={100}
                step={100}
                value={amountCents}
                onChange={(e) => setAmountCents(e.target.value)}
                className="rounded-md border px-3 py-2 text-sm bg-background w-40"
              />
              <Button type="submit" size="sm">
                <Plus className="h-3.5 w-3.5 mr-1" />
                {t("meal.topup")}
              </Button>
            </form>
          </>
        )}
      </CardContent>
    </Card>
  );
}


// ─── Donations ─────────────────────────────────────────────────────


function DonationsSection() {
  const t = useTranslations("parentMore");
  const [history, setHistory] = useState<DonationRow[]>([]);
  const [refresh, setRefresh] = useState(0);
  const [amountCents, setAmountCents] = useState("1000");
  const [purpose, setPurpose] = useState("");
  const [anonymous, setAnonymous] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const r = await fetchJson<DonationRow[]>("/api/v1/donations");
        setHistory(r.data);
      } catch {
        setHistory([]);
      }
    })();
  }, [refresh]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const r = await postJson("/api/v1/donations", {
      amount_cents: Number(amountCents),
      purpose: purpose.trim() || undefined,
      anonymous,
    });
    if (r.ok) {
      setPurpose("");
      setRefresh((n) => n + 1);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <HandCoins className="h-4 w-4" /> {t("donations.title")}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <form onSubmit={submit} className="space-y-2">
          <div className="grid grid-cols-2 gap-2">
            <input
              type="number"
              min={100}
              step={100}
              value={amountCents}
              onChange={(e) => setAmountCents(e.target.value)}
              className="rounded-md border px-3 py-2 text-sm bg-background"
            />
            <input
              type="text"
              value={purpose}
              onChange={(e) => setPurpose(e.target.value)}
              placeholder={t("donations.purposePlaceholder")}
              className="rounded-md border px-3 py-2 text-sm bg-background"
            />
          </div>
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            <input
              type="checkbox"
              checked={anonymous}
              onChange={(e) => setAnonymous(e.target.checked)}
            />
            {t("donations.anonymous")}
          </label>
          <Button type="submit" size="sm">
            {t("donations.submit")}
          </Button>
        </form>

        {history.length > 0 && (
          <ul className="space-y-1 text-xs text-muted-foreground">
            {history.map((d) => (
              <li key={d.id} className="flex justify-between">
                <span>
                  {(d.amount_cents / 100).toFixed(2)} {d.currency}
                  {d.purpose ? ` · ${d.purpose}` : ""}
                </span>
                <span>{new Date(d.created_at).toLocaleDateString()}</span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}


// ─── Newsletter ────────────────────────────────────────────────────


function NewsletterSection() {
  const t = useTranslations("parentMore");
  const [posts, setPosts] = useState<NewsletterPost[]>([]);

  useEffect(() => {
    (async () => {
      try {
        const r = await fetchJson<NewsletterPost[]>("/api/v1/newsletter");
        setPosts(r.data);
      } catch {
        setPosts([]);
      }
    })();
  }, []);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Newspaper className="h-4 w-4" /> {t("newsletter.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {posts.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            {t("newsletter.empty")}
          </p>
        ) : (
          <ul className="space-y-3">
            {posts.map((p) => (
              <li key={p.id}>
                <div className="font-medium text-sm">{p.title}</div>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {new Date(p.published_at).toLocaleDateString()}
                </p>
                <p className="text-sm mt-1 whitespace-pre-wrap">{p.body}</p>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}


// ─── Gallery ───────────────────────────────────────────────────────


function GallerySection() {
  const t = useTranslations("parentMore");
  const [items, setItems] = useState<GalleryItem[]>([]);

  useEffect(() => {
    (async () => {
      try {
        const r = await fetchJson<GalleryItem[]>("/api/v1/gallery");
        setItems(r.data);
      } catch {
        setItems([]);
      }
    })();
  }, []);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <ImageIcon className="h-4 w-4" /> {t("gallery.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {items.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("gallery.empty")}</p>
        ) : (
          <ul className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {items.map((g) => (
              <li key={g.id} className="border rounded-md overflow-hidden">
                <div className="aspect-square bg-muted flex items-center justify-center">
                  <ImageIcon className="h-8 w-8 text-muted-foreground" />
                </div>
                {g.caption && (
                  <div className="p-2 text-xs">{g.caption}</div>
                )}
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
