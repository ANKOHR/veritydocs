import "./globals.css";

export const metadata = {
  title: "VerityDocs — Evidence-backed document intelligence",
  description: "Turn messy documents into trusted, reconciled records.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
