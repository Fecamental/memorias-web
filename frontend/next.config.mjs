const backend = process.env.MEMORIAS_BACKEND || "http://127.0.0.1:14801";

const local = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: backend + "/:path*" }];
  },
};

export default process.env.MEMORIAS_STATIC === "1"
  ? { output: "export", distDir: ".next-portable" }
  : local;
