import {Composition, registerRoot} from 'remotion';
import {NourbitPremiumShort, NourbitShort, nourbitPremiumSchema, nourbitShortSchema} from './nourbit-short';

const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="NourbitShort"
        component={NourbitShort}
        durationInFrames={90}
        fps={30}
        width={1080}
        height={1920}
        schema={nourbitShortSchema}
        defaultProps={{
          titleHook: 'Untuk Siapa Ibadah Kita?',
          captionText: 'Ketika seseorang memperbaiki niat, amal yang kecil bisa menjadi besar.',
          watermarkText: 'Nourbit Clips',
          ctaText: 'Follow Nourbit untuk nasihat singkat lainnya',
        }}
      />
      <Composition
        id="NourbitPremiumShort"
        component={NourbitPremiumShort}
        durationInFrames={3600}
        fps={30}
        width={1080}
        height={1920}
        schema={nourbitPremiumSchema}
        calculateMetadata={({props}) => ({
          durationInFrames: Math.max(1, Math.ceil((props.durationMs / 1000) * 30)),
        })}
        defaultProps={{
          durationMs: 120000,
          sourceVideoPath: 'runtime/sample/source.mp4',
          sourceAttribution: 'Source: Ribath Nouraniyyah Hasyimiyyah',
          titleHook: 'Kenapa Hati Masih Kesepian?',
          subtitle: 'Momen ini kuat karena menyentuh keresahan batin dengan jawaban yang sederhana.',
          captions: [
            {
              text: 'Allah selalu bersama dengan kita',
              startMs: 0,
              endMs: 4000,
              timestampMs: 0,
              confidence: null,
            },
          ],
          visualBeats: [
            {type: 'hook', startMs: 0, endMs: 4500},
            {type: 'caption_emphasis', startMs: 5500, endMs: 111000},
            {type: 'cta', startMs: 113500, endMs: 120000},
          ],
          watermarkText: 'Nourbit Clips',
          ctaText: 'Follow Nourbit untuk nasihat singkat lainnya',
        }}
      />
    </>
  );
};

registerRoot(RemotionRoot);
