import { defineConfig } from "vite-plus";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
    plugins: [react()],
    test: {
        environment: "jsdom",
        globals: true,
        setupFiles: ["./vitest.setup.ts"],
        pool: "threads",
    },
    resolve: {
        alias: {
            "@": path.resolve(import.meta.dirname, "./"),
        },
    },
});
