import { promises as fs } from "node:fs";
import path from "node:path";

export const dynamic = "force-dynamic";

export async function GET(): Promise<Response> {
  const htmlPath = path.join(process.cwd(), "public", "index.html");
  const html = await fs.readFile(htmlPath, "utf-8");
  return new Response(html, {
    status: 200,
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      "Cache-Control": "no-store",
    },
  });
}
