/**
 * LinkButton — Phase 19c primitive (audit fix C4).
 *
 * The codebase had 8 sites doing `<Button><Link>...</Link></Button>`,
 * which renders the invalid HTML `<button><a>...</a></button>`. That
 * breaks keyboard navigation (Enter/Space on the button doesn't follow
 * the link), accessibility tree, and SSR semantics.
 *
 * This component takes the same visual variants as `Button` but renders
 * a real `<a>` tag — so callers that "want a link styled as a button"
 * get one valid element with the right semantics.
 *
 * Usage:
 *   <LinkButton href="/curriculum">Curriculum</LinkButton>
 *   <LinkButton href="/foo" variant="outline" size="sm">Foo</LinkButton>
 *
 * If you need Next.js client-side navigation, wrap the LinkButton in a
 * Next `<Link>` with `legacyBehavior passHref` — but in practice the
 * plain `<a>` works fine on internal hrefs and we sidestep the
 * Link/passHref dance.
 */
import * as React from "react";
import { cn } from "../lib/utils";
import { buttonVariants } from "./button";
import type { VariantProps } from "class-variance-authority";

export interface LinkButtonProps
  extends React.AnchorHTMLAttributes<HTMLAnchorElement>,
    VariantProps<typeof buttonVariants> {
  href: string;
}

const LinkButton = React.forwardRef<HTMLAnchorElement, LinkButtonProps>(
  ({ className, variant, size, children, ...props }, ref) => {
    return (
      <a
        ref={ref}
        className={cn(buttonVariants({ variant, size, className }))}
        {...props}
      >
        {children}
      </a>
    );
  }
);
LinkButton.displayName = "LinkButton";

export { LinkButton };
