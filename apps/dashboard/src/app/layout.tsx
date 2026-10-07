import type {Metadata} from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Otonom Media",
  description:
    "Open-source brand brain plus factory: publish-ready social content across text, stills, carousels, shorts, long-form, and clips.",
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
