import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  transpilePackages: ['@voice-support/widget', '@voice-support/contracts'],
};

export default nextConfig;
