import TrendClient from './TrendClient';

export default async function Page({
  params,
}: {
  params: Promise<{ analysisId: string }>;
}) {
  const { analysisId } = await params;
  return <TrendClient analysisId={analysisId} />;
}