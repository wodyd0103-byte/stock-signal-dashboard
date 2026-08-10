import nextCoreWebVitals from "eslint-config-next/core-web-vitals";

// Next.js 16 removed `next lint`, so ESLint runs through its own CLI and needs a
// flat config. `eslint-config-next/core-web-vitals` already bundles the base
// `next` and `next/typescript` configs, so it is the only preset needed here.
const config = [
  {
    ignores: [".next/**", "out/**", "node_modules/**", "next-env.d.ts"],
  },
  ...nextCoreWebVitals,
];

export default config;
