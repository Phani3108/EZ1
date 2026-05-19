/**
 * Admin navigation configuration — clean Information Architecture.
 *
 * 5 sections:
 *   Dashboard  → school KPIs
 *   Academics  → years, terms, classes, subjects
 *   People     → students, parents, teachers, users & roles
 *   Operations → attendance, fees, communication
 *   Intelligence → reports (+ dropout/insights later)
 *
 * Each item declares the permission needed to see it.
 * "authenticated" = any logged-in user.
 */

import {
  LayoutDashboard,
  GraduationCap,
  Users,
  Briefcase,
  BarChart3,
  Landmark,
  ClipboardList,
  ServerCog,
  Map,
  School,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  title: string;
  href: string;
  icon: LucideIcon;
  permission: string; // "authenticated" | "school:manage" | etc.
  children?: { title: string; href: string; permission: string }[];
}

export const adminNav: NavItem[] = [
  // ─── Dashboard ───
  {
    title: "Dashboard",
    href: "/dashboard",
    icon: LayoutDashboard,
    permission: "authenticated",
  },

  // ─── Academics ───
  {
    title: "Academics",
    href: "/academics",
    icon: GraduationCap,
    permission: "authenticated",
    children: [
      { title: "Academic Years", href: "/academics/years", permission: "authenticated" },
      { title: "Terms", href: "/academics/terms", permission: "authenticated" },
      { title: "Classes", href: "/classes", permission: "authenticated" },
      { title: "Subjects", href: "/subjects", permission: "authenticated" },
    ],
  },

  // ─── People ───
  {
    title: "People",
    href: "/students",
    icon: Users,
    permission: "authenticated",
    children: [
      { title: "Students", href: "/students", permission: "student:read" },
      { title: "Parents", href: "/parents", permission: "student:read" },
      { title: "Teachers", href: "/teachers", permission: "authenticated" },
      { title: "Users & Roles", href: "/users", permission: "school:manage" },
    ],
  },

  // ─── Operations ───
  {
    title: "Operations",
    href: "/attendance",
    icon: Briefcase,
    permission: "authenticated",
    children: [
      { title: "Daily Attendance", href: "/attendance", permission: "attendance:read" },
      { title: "Sync Monitor", href: "/attendance/sync-monitor", permission: "school:manage" },
      { title: "Assessments", href: "/assessments", permission: "assessment:read" },
      { title: "Enrollments", href: "/enrollments", permission: "student:write" },
      { title: "Fee Structures", href: "/fees/structures", permission: "fees:read" },
      { title: "Invoices", href: "/fees/invoices", permission: "fees:read" },
      { title: "Defaulters", href: "/fees/defaulters", permission: "fees:read" },
      { title: "Announcements", href: "/communication/announcements", permission: "comm:read" },
      { title: "Outbox", href: "/communication/outbox", permission: "school:manage" },
    ],
  },

  // ─── Intelligence ───
  {
    title: "Intelligence",
    href: "/reports",
    icon: BarChart3,
    permission: "authenticated",
    children: [
      { title: "Reports", href: "/reports", permission: "report:read" },
      { title: "Dropout Risk", href: "/intelligence/dropout", permission: "report:read" },
    ],
  },

  // ─── National Alignment ───
  {
    title: "National Alignment",
    href: "/national-alignment",
    icon: Landmark,
    permission: "authenticated",
  },

  // ─── National Network ───
  {
    title: "Network",
    href: "/provinces",
    icon: Map,
    permission: "authenticated",
    children: [
      { title: "Provinces", href: "/provinces", permission: "authenticated" },
      { title: "Schools",   href: "/schools",   permission: "authenticated" },
    ],
  },

  // ─── System ───
  {
    title: "System",
    href: "/integrations",
    icon: ServerCog,
    permission: "report:admin",
    children: [
      { title: "Integrations", href: "/integrations", permission: "report:admin" },
    ],
  },
];
