/** @type {import('next').NextConfig} */
const nextConfig = {
  // Fully static export: no server runtime, no API routes — consistent with
  // DESIGN.md §1 decision #4 ("no API call" crossing from local to public).
  output: "export",
  images: { unoptimized: true },
  // ui/dashboard/ is self-contained (Phase 0 copy step), so no `..` fs reads.
  trailingSlash: true,
};

export default nextConfig;
