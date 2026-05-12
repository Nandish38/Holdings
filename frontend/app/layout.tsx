import Link from "next/link";
import "./styles.css";

const nav = [
  ["Dashboard", "/"],
  ["Portfolio", "/portfolio"],
  ["Returns", "/returns"],
  ["Markets", "/markets"],
  ["Activity", "/activity"],
  ["Journal", "/journal"],
  ["Goals", "/goals"],
  ["Alerts", "/alerts"]
];

export const metadata = {
  title: "Vaultboard",
  description: "Portfolio dashboard powered by FastAPI and Next.js"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="appShell">
          <aside className="sidebar">
            <div className="brand">
              <span>Vaultboard</span>
              <small>Next.js + FastAPI</small>
            </div>
            <nav>
              {nav.map(([label, href]) => (
                <Link href={href} key={href}>
                  {label}
                </Link>
              ))}
            </nav>
          </aside>
          <main className="content">{children}</main>
        </div>
      </body>
    </html>
  );
}
