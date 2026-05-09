import {Audio, AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {z} from 'zod';

export const nourbitShortSchema = z.object({
  titleHook: z.string(),
  captionText: z.string(),
  watermarkText: z.string(),
  ctaText: z.string(),
});

type Props = z.infer<typeof nourbitShortSchema>;

export const NourbitShort: React.FC<Props> = ({titleHook, captionText, watermarkText, ctaText}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const titleScale = spring({frame, fps, config: {damping: 16, stiffness: 120}});
  const captionY = interpolate(frame, [0, 24], [80, 0], {extrapolateRight: 'clamp'});
  const words = captionText.split(' ');
  const visibleWords = words.slice(0, Math.max(1, Math.floor(frame / 4))).join(' ');

  return (
    <AbsoluteFill style={{backgroundColor: '#111111', color: 'white', fontFamily: 'Inter, Arial, sans-serif'}}>
      <Audio src="https://remotion.media/whoosh.wav" startFrom={0} volume={0.18} />
      <div style={{
        position: 'absolute',
        top: 260,
        left: 90,
        right: 90,
        transform: `scale(${titleScale})`,
        fontSize: 76,
        lineHeight: 1.05,
        fontWeight: 800,
        textAlign: 'center',
      }}>
        {titleHook}
      </div>
      <div style={{
        position: 'absolute',
        left: 80,
        right: 80,
        bottom: 560 + captionY,
        padding: '24px 28px',
        borderRadius: 18,
        backgroundColor: 'rgba(0, 0, 0, 0.58)',
        fontSize: 48,
        lineHeight: 1.18,
        fontWeight: 700,
        textAlign: 'center',
      }}>
        {visibleWords}
      </div>
      <div style={{position: 'absolute', left: 0, right: 0, bottom: 210, textAlign: 'center', fontSize: 34, opacity: 0.86}}>
        {watermarkText}
      </div>
      <div style={{position: 'absolute', left: 80, right: 80, bottom: 130, textAlign: 'center', fontSize: 36, color: '#f4d35e', fontWeight: 700}}>
        {ctaText}
      </div>
    </AbsoluteFill>
  );
};
