import {BrandBuilderPage} from "@/components/brand/BrandBuilderWorkspace";

type BuilderPageProps = {
  searchParams: Promise<{
    starter?: string;
    preset?: string;
    base?: string;
  }>;
};

export default async function BrandBuilderRoute({searchParams}: BuilderPageProps) {
  const {starter, preset, base} = await searchParams;
  return <BrandBuilderPage starter={starter} preset={preset} baseTemplate={base} />;
}
