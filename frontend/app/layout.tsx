import { SidebarNav } from "@/components/SidebarNav";
import "./styles.css";

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
            <SidebarNav />
          </aside>
          <main className="content">{children}</main>
        </div>
      </body>
    </html>
  );
}
