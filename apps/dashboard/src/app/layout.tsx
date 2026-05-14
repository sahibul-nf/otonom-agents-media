import type {Metadata} from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Otonom Media Dashboard",
  description: "Autonomous media operations dashboard for Nourbit and future brands.",
};

export default function RootLayout({children}: Readonly<{children: React.ReactNode}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body suppressHydrationWarning>{children}</body>
    </html>
  );
}
