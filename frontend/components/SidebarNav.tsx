"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const nav: Array<[string, string]> = [
  ["Dashboard", "/"],
  ["Portfolio", "/portfolio"],
  ["Returns", "/returns"],
  ["Markets", "/markets"],
  ["Activity", "/activity"],
  ["Journal", "/journal"],
  ["Goals", "/goals"],
  ["Alerts", "/alerts"]
];

function isActive(pathname: string, href: string): boolean {
  if (href === "/") {
    return pathname === "/";
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function SidebarNav() {
  const pathname = usePathname() || "/";

  return (
    <nav className="sidebarNav">
      {nav.map(([label, href]) => (
        <Link
          key={href}
          href={href}
          prefetch
          className={isActive(pathname, href) ? "navLink active" : "navLink"}
        >
          {label}
        </Link>
      ))}
    </nav>
  );
}
