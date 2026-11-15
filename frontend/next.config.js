/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    const backendUrl = process.env.BACKEND_URL;
    if (!backendUrl && process.env.NODE_ENV !== 'development') {
      return [];
    }
    const target = backendUrl || 'http://127.0.0.1:8000';
    return [
      {
        source: '/api/:path*',
        destination: `${target}/api/:path*`,
      },
      {
        source: '/health',
        destination: `${target}/health`,
      },
      {
        source: '/mcp/:path*',
        destination: `${target}/mcp/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
