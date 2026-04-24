import type { NextConfig } from 'next';

const backendUrl = process.env.RESUME_COPILOT_BACKEND_URL ?? 'http://127.0.0.1:8002';

const nextConfig: NextConfig = {
  allowedDevOrigins: ['127.0.0.1', 'localhost'],
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
