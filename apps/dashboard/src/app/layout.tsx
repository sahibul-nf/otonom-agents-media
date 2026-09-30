import type {Metadata} from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Otonom Media Studio OS",
  description: "Autonomous media operations dashboard for public multi-brand video production.",
};

export default function RootLayout({children}: Readonly<{children: React.ReactNode}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body suppressHydrationWarning>
        <script
          dangerouslySetInnerHTML={{
            __html: `(()=>{try{if(window.matchMedia("(prefers-color-scheme: light)").matches)document.documentElement.classList.add("light-theme")}catch(e){}})()`,
          }}
        />
        {children}
      </body>
    </html>
  );
}
