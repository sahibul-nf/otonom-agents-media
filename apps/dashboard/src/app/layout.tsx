import type {Metadata} from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Otonom Media Studio OS",
  description: "Autonomous media operations dashboard for public multi-brand video production.",
};

export default function RootLayout({children}: Readonly<{children: React.ReactNode}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body suppressHydrationWarning>{children}</body>
    </html>
  );
}
