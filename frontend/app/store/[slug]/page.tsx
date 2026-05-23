import { StoreTemplate } from "@/components/StoreTemplate";
import { getStore } from "@/lib/api";

export default async function StorePage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const store = await getStore(slug);
  return <StoreTemplate store={store} />;
}
