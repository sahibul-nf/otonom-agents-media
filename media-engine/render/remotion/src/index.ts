import {Composition} from 'remotion';
import {NourbitShort, nourbitShortSchema} from './nourbit-short';

export const RemotionRoot: React.FC = () => {
  return (
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
  );
};
