import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#16201d",
        moss: "#416555",
        mint: "#dff6ec",
        coral: "#ef6f61",
        amber: "#f8c85f",
      },
      boxShadow: {
        panel: "0 18px 60px rgba(22, 32, 29, 0.12)",
      },
    },
  },
  plugins: [],
} satisfies Config;
