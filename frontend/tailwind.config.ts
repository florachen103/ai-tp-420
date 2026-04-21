import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        /** 高济红 / 高济橙：主色保留，浅阶降饱和，便于大面积留白与长时间阅读 */
        brand: {
          50: "#faf7f7",
          100: "#f2eaea",
          200: "#e5d6d8",
          300: "#c4a8ad",
          400: "#EC6A3E",
          500: "#E60036",
          600: "#c4002e",
          700: "#9e0025",
          900: "#4a1418",
        },
      },
      fontFamily: {
        sans: [
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "BlinkMacSystemFont",
          "PingFang SC",
          "Microsoft YaHei",
          "sans-serif",
        ],
      },
    },
  },
  plugins: [],
};
export default config;
