import {ReviewEditorPage} from "@/components/review/ReviewEditorPage";

export default async function ClipReviewPage({
  params,
  searchParams,
}: {
  params: Promise<{clipId: string}>;
  searchParams: Promise<{from?: string; sourceId?: string}>;
}) {
  const {clipId} = await params;
  const query = await searchParams;
  const fromBatch = query.from === "batch";
  const batchSourceId = typeof query.sourceId === "string" ? query.sourceId : "";
  return (
    <ReviewEditorPage
      clipId={decodeURIComponent(clipId)}
      fromBatch={fromBatch}
      batchSourceId={batchSourceId}
    />
  );
}
