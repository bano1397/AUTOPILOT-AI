/** @type {import('next').NextConfig} */
const nextConfig = {
  // Emit a minimal standalone server for small production Docker images.
  output: "standalone",
};

export default nextConfig;
