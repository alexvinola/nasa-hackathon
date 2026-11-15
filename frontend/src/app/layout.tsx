import type { Metadata } from "next";
import "./globals.css";
// Server component: it imports the dictionaries, not "@/i18n", whose hooks only run on the client.
import { messages } from "@/i18n/messages";

const DEFAULT_LANG = process.env.NEXT_PUBLIC_LANG === "en" ? "en" : "es";
const t = (key: "app.title" | "app.description") => messages[DEFAULT_LANG][key];

// Metadata is rendered on the server, so it follows NEXT_PUBLIC_LANG; the HUD's ES | EN switch changes the rest.
export const metadata: Metadata = {
  title: t("app.title"),
  description: t("app.description"),
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang={DEFAULT_LANG}>
      <body>{children}</body>
    </html>
  );
}
