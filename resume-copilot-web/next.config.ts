import type { NextConfig } from 'next';

const backendUrl = process.env.RESUME_COPILOT_BACKEND_URL ?? 'http://127.0.0.1:8002';

const nextConfig: NextConfig = {
  allowedDevOrigins: ['127.0.0.1', 'localhost', '10.0.0.12'],
  devIndicators: false,
  // Default Next proxy timeout = 30s; teacher-entry batch OCR + 5 LLM calls
  // under DeepSeek slow-moments can spike to 25-40s. 120s buys headroom
  // without making real hangs invisible.
  experimental: {
    proxyTimeout: 120_000,
  },
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
