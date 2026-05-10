import type { Metadata } from 'next';
import './styles.css';

export const metadata: Metadata = {
  title: 'Voice Support Demo',
  description: 'Demo site and operator console for the OSS voice support bot.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
