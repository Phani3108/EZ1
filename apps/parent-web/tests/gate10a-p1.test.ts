/**
 * Parent-web — Unit Tests for 10A-P1 (Parents Me Children)
 *
 * Covers:
 *  ✅ API client has getMyChildren() method
 *  ✅ getMyChildren() calls GET /api/v1/parents/me/children
 *  ✅ Home page file exists
 *  ✅ Children detail page file exists at /children/[id]/page.tsx
 *  ✅ useApiQuery hook exists in parent-web
 *  ✅ Error utilities exist in parent-web
 */
import { describe, it, expect, vi } from "vitest";
import * as fs from "fs";
import * as path from "path";

// ─── 1. API client getMyChildren method ───

import { studentApi } from "@eduzim/api-client";

describe("API client — getMyChildren method", () => {
  const mockClient = {
    get: vi.fn().mockResolvedValue({ data: [] }),
    post: vi.fn().mockResolvedValue({ data: {} }),
    put: vi.fn().mockResolvedValue({ data: {} }),
    delete: vi.fn().mockResolvedValue({ data: null }),
  };

  it("studentApi exposes getMyChildren", () => {
    const svc = studentApi(mockClient as any);
    expect(typeof svc.getMyChildren).toBe("function");
  });

  it("getMyChildren calls GET /api/v1/parents/me/children", async () => {
    const svc = studentApi(mockClient as any);
    await svc.getMyChildren();
    expect(mockClient.get).toHaveBeenCalledWith(
      "/api/v1/parents/me/children"
    );
  });

  it("getParentChildren still works (admin use case)", () => {
    const svc = studentApi(mockClient as any);
    expect(typeof svc.getParentChildren).toBe("function");
  });
});

// ─── 2. File structure ───

describe("10A-P1 file structure", () => {
  const parentWebSrc = path.resolve(__dirname, "../src");

  it("home page exists", () => {
    expect(
      fs.existsSync(path.join(parentWebSrc, "app/(parent)/home/page.tsx"))
    ).toBe(true);
  });

  it("children/[id] detail page exists", () => {
    expect(
      fs.existsSync(
        path.join(parentWebSrc, "app/(parent)/children/[id]/page.tsx")
      )
    ).toBe(true);
  });

  it("useApiQuery hook exists", () => {
    expect(
      fs.existsSync(path.join(parentWebSrc, "hooks/use-api-query.ts"))
    ).toBe(true);
  });

  it("error utilities exist", () => {
    expect(
      fs.existsSync(path.join(parentWebSrc, "lib/errors.ts"))
    ).toBe(true);
  });
});

// ─── 3. Home page content ───

describe("Home page content", () => {
  const homePath = path.resolve(
    __dirname,
    "../src/app/(parent)/home/page.tsx"
  );
  const homeContent = fs.readFileSync(homePath, "utf-8");

  it("calls getMyChildren", () => {
    expect(homeContent).toContain("getMyChildren");
  });

  it("renders children list with links to /children/", () => {
    expect(homeContent).toContain("/children/");
  });

  it("shows loading state", () => {
    expect(homeContent).toContain("isLoading");
  });

  it("shows error state", () => {
    expect(homeContent).toContain("error");
  });

  it("shows empty state when no children", () => {
    // Home page uses next-intl; source references the empty-state component and i18n key.
    expect(homeContent).toMatch(/IllustratedEmptyState|noChildren/);
  });
});

// ─── 4. Children detail page content ───

describe("Child detail page content", () => {
  const detailPath = path.resolve(
    __dirname,
    "../src/app/(parent)/children/[id]/page.tsx"
  );
  const detailContent = fs.readFileSync(detailPath, "utf-8");

  it("uses useParams to get child id", () => {
    expect(detailContent).toContain("useParams");
  });

  it("fetches children via getMyChildren", () => {
    expect(detailContent).toContain("getMyChildren");
  });

  it("displays student information card", () => {
    expect(detailContent).toContain("Student Information");
  });

  it("has a back navigation to home", () => {
    expect(detailContent).toContain("/home");
  });
});
