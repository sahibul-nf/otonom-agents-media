import {BrandBuilderPage} from "@/components/brand/BrandBuilderWorkspace";

type BuilderPageProps = {
  searchParams: Promise<{
    starter?: string;
    preset?: string;
    base?: string;
    duplicate?: string;
  }>;
};

export default async function BrandBuilderRoute({searchParams}: BuilderPageProps) {
  const {starter, preset, base, duplicate} = await searchParams;
  return <BrandBuilderPage starter={starter} preset={preset} baseTemplate={base} duplicate={duplicate === "1"} />;
}
