/** @type {import('next').NextConfig} */
const nextConfig = {
  experimental: {
    typedRoutes: true,
    serverActions: { allowedOrigins: ['*'] }
  }
};
export default nextConfig;
