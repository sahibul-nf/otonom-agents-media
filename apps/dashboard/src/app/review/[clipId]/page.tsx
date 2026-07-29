import {ReviewEditorPage} from "@/components/review/ReviewEditorPage";

export default async function ClipReviewPage({params}: {params: Promise<{clipId: string}>}) {
  const {clipId} = await params;
  return <ReviewEditorPage clipId={decodeURIComponent(clipId)} />;
}
