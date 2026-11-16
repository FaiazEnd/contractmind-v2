/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    // Under Vercel Services (`vercel dev` or Vercel deployments), top-level `vercel.json`
    // rewrites route `/api/*`, `/mcp*`, and `/health` directly to the `backend` service.
    // Only proxy to localhost when running `next dev` standalone outside Vercel.
    if (process.env.VERCEL || process.env.NODE_ENV !== 'development') {
      return [];
    }
    const target = 'http://127.0.0.1:8000';
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
        source: '/mcp',
        destination: `${target}/mcp`,
      },
      {
        source: '/mcp/:path*',
        destination: `${target}/mcp/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
