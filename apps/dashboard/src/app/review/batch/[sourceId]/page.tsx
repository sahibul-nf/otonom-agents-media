import {ReviewBatchPage} from "@/components/review/ReviewBatchPage";

export default async function ReviewBatchRoutePage({params}: {params: Promise<{sourceId: string}>}) {
  const {sourceId} = await params;
  return <ReviewBatchPage sourceId={decodeURIComponent(sourceId)} />;
}
