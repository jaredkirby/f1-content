import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {
  title: "Race Notes — Phone Review",
  description: "Watch, annotate and review the Singapore qualifying pilot.",
  icons: { icon: "/favicon.svg" },
};
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="en"><body>{children}</body></html>;
}
