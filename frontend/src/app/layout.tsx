import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PULSAR",
  description: "Tu compañero personal de salud en el espacio.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body>{children}</body>
    </html>
  );
}
