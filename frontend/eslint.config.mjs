import nextCoreWebVitals from "eslint-config-next/core-web-vitals";
import prettier from "eslint-config-prettier/flat";

// Next.js 16 removed `next lint`, so ESLint runs through its own CLI and needs a
// flat config. `eslint-config-next/core-web-vitals` already bundles the base
// `next` and `next/typescript` configs, so it is the only preset needed here.
const config = [
  {
    ignores: [".next/**", "out/**", "node_modules/**", "next-env.d.ts"],
  },
  ...nextCoreWebVitals,
  // Formatting belongs to Prettier, so switch off any ESLint rule that would
  // disagree with it. Must stay last to win over the presets above.
  prettier,
];

export default config;
