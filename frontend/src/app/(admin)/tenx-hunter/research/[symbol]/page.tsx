import { redirect } from "next/navigation";

export default async function TenxHunterResearchRedirectPage({ params }: { params: Promise<{ symbol: string }> }) {
  const { symbol } = await params;
  redirect(`/tenx-hunter/cn/research/${symbol}`);
}
