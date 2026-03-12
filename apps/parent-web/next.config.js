const createNextIntlPlugin = require("next-intl/plugin");

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

/** @type {import('next').NextConfig} */
const nextConfig = {
  transpilePackages: ["@eduzim/ui", "@eduzim/api-client", "@eduzim/auth"],
};

module.exports = withNextIntl(nextConfig);
