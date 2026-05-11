import {
  AbsoluteFill,
  Audio,
  Video,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import {z} from 'zod';

const wordSchema = z.object({
  text: z.string(),
  startMs: z.number(),
  endMs: z.number(),
  highlight: z.boolean().optional(),
});

const captionSchema = z.object({
  text: z.string(),
  startMs: z.number(),
  endMs: z.number(),
  timestampMs: z.number().nullable(),
  confidence: z.number().nullable(),
  words: z.array(wordSchema).optional(),
});

const visualBeatSchema = z.object({
  type: z.string(),
  startMs: z.number(),
  endMs: z.number(),
});

export const nourbitShortSchema = z.object({
  titleHook: z.string(),
  captionText: z.string(),
  watermarkText: z.string(),
  ctaText: z.string(),
  style: z.any().optional(),
});

export const nourbitPremiumSchema = z.object({
  durationMs: z.number(),
  sourceVideoPath: z.string(),
  sourceAttribution: z.string(),
  titleHook: z.string(),
  subtitle: z.string(),
  captions: z.array(captionSchema),
  visualBeats: z.array(visualBeatSchema),
  watermarkText: z.string(),
  ctaText: z.string(),
});

type BasicProps = z.infer<typeof nourbitShortSchema>;
type PremiumProps = z.infer<typeof nourbitPremiumSchema>;

const font = 'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
const gold = '#f4d35e';
const green = '#9be7b0';

export const NourbitShort: React.FC<BasicProps> = ({titleHook, captionText, watermarkText, ctaText}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const titleScale = spring({frame, fps, config: {damping: 16, stiffness: 120}});
  const captionY = interpolate(frame, [0, 24], [80, 0], {extrapolateRight: 'clamp'});
  const words = captionText.split(' ');
  const visibleWords = words.slice(0, Math.max(1, Math.floor(frame / 4))).join(' ');

  return (
    <AbsoluteFill style={{backgroundColor: '#111111', color: 'white', fontFamily: font}}>
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
      <div style={{position: 'absolute', left: 80, right: 80, bottom: 130, textAlign: 'center', fontSize: 36, color: gold, fontWeight: 700}}>
        {ctaText}
      </div>
    </AbsoluteFill>
  );
};

const msToFrame = (ms: number, fps: number) => Math.round((ms / 1000) * fps);

const getActiveCaption = (captions: PremiumProps['captions'], currentMs: number) => {
  return captions.find((caption) => currentMs >= caption.startMs && currentMs < caption.endMs) ?? captions[0];
};

const emphasizeCaption = (caption: PremiumProps['captions'][number], currentMs: number, highlightColor: string) => {
  const words = caption.words ?? caption.text.split(' ').map((text) => ({text, startMs: caption.startMs, endMs: caption.endMs}));
  const activeIndex = Math.max(0, words.findIndex((word) => currentMs >= word.startMs && currentMs < word.endMs));
  return (
    <>
      {words.map((word, index) => (
        <span
          key={`${word.text}-${index}`}
          style={{
            color: index === activeIndex || word.highlight ? highlightColor : 'white',
            display: 'inline-block',
            transform: index === activeIndex ? 'translateY(-2px) scale(1.08)' : 'translateY(0) scale(1)',
            transition: 'transform 90ms ease, color 90ms ease',
          }}
        >
          {word.text}{index === words.length - 1 ? '' : ' '}
        </span>
      ))}
    </>
  );
};

export const NourbitPremiumShort: React.FC<PremiumProps> = ({
  durationMs,
  sourceVideoPath,
  sourceAttribution,
  titleHook,
  subtitle,
  captions,
  visualBeats,
  watermarkText,
  ctaText,
  style,
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const currentMs = (frame / fps) * 1000;
  const activeCaption = getActiveCaption(captions, currentMs);
  const hookBeat = visualBeats.find((beat) => beat.type === 'hook');
  const ctaBeat = visualBeats.find((beat) => beat.type === 'cta');
  const hookEndFrame = msToFrame(hookBeat?.endMs ?? 4500, fps);
  const ctaStartFrame = msToFrame(ctaBeat?.startMs ?? Math.max(0, durationMs - 6500), fps);
  const entrance = spring({frame, fps, config: {damping: 18, stiffness: 120}});
  const hookOpacity = interpolate(frame, [0, 16, hookEndFrame - 10, hookEndFrame], [0, 1, 1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const captionLift = activeCaption
    ? spring({frame: Math.max(0, frame - msToFrame(activeCaption.startMs, fps)), fps, config: {damping: 18, stiffness: 170}})
    : 1;
  const ctaOpacity = interpolate(frame, [ctaStartFrame, ctaStartFrame + 18], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const slowZoom = interpolate(frame, [0, Math.max(1, msToFrame(durationMs, fps))], [1.03, 1.12], {
    extrapolateRight: 'clamp',
  });
  const captionStyle = style?.caption ?? {};
  const highlightColor = captionStyle.highlight_word_color ?? '#00ff36';
  const captionFontSize = captionStyle.font_size ?? 54;

  return (
    <AbsoluteFill style={{backgroundColor: '#050607', color: 'white', fontFamily: font, overflow: 'hidden'}}>
      <Video
        src={staticFile(sourceVideoPath)}
        style={{
          width: '100%',
          height: '100%',
          objectFit: 'cover',
          transform: `scale(${slowZoom})`,
          filter: 'contrast(1.06) saturate(0.96) brightness(0.92)',
        }}
      />
      <AbsoluteFill
        style={{
          background:
            'linear-gradient(180deg, rgba(0,0,0,0.58) 0%, rgba(0,0,0,0.12) 28%, rgba(0,0,0,0.18) 55%, rgba(0,0,0,0.74) 100%)',
        }}
      />
      <div
        style={{
          position: 'absolute',
          top: 170,
          left: 72,
          right: 72,
          opacity: hookOpacity,
          transform: `translateY(${interpolate(entrance, [0, 1], [36, 0])}px) scale(${interpolate(entrance, [0, 1], [0.96, 1])})`,
          textAlign: 'center',
        }}
      >
        <div
          style={{
            fontSize: 74,
            lineHeight: 0.98,
            fontWeight: 900,
            textShadow: '0 5px 24px rgba(0,0,0,0.72)',
          }}
        >
          {titleHook}
        </div>
        <div
          style={{
            marginTop: 22,
            fontSize: 30,
            lineHeight: 1.18,
            color: 'rgba(255,255,255,0.84)',
            fontWeight: 650,
          }}
        >
          {subtitle}
        </div>
      </div>

      {activeCaption ? (
        <div
          style={{
            position: 'absolute',
            left: 62,
            right: 62,
            bottom: 365,
            padding: '22px 28px 24px',
            borderRadius: 16,
            border: '1px solid rgba(255,255,255,0.16)',
            backgroundColor: 'rgba(4, 7, 8, 0.72)',
            boxShadow: '0 18px 48px rgba(0,0,0,0.42)',
            transform: `translateY(${interpolate(captionLift, [0, 1], [26, 0])}px)`,
            textAlign: 'center',
          }}
        >
          <div style={{fontSize: captionFontSize, lineHeight: 1.08, fontWeight: 900, textShadow: '0 3px 12px rgba(0,0,0,0.9)'}}>
            {emphasizeCaption(activeCaption, currentMs, highlightColor)}
          </div>
        </div>
      ) : null}

      <div
        style={{
          position: 'absolute',
          left: 48,
          right: 48,
          bottom: 230,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: 22,
          fontSize: 25,
          color: 'rgba(255,255,255,0.82)',
          fontWeight: 700,
          textShadow: '0 2px 10px rgba(0,0,0,0.8)',
        }}
      >
        <span>{watermarkText}</span>
        <span style={{color: green}}>{sourceAttribution}</span>
      </div>

      <div
        style={{
          position: 'absolute',
          left: 62,
          right: 62,
          bottom: 95,
          opacity: ctaOpacity,
          padding: '22px 26px',
          borderRadius: 18,
          backgroundColor: 'rgba(0, 0, 0, 0.68)',
          border: `2px solid ${gold}`,
          color: gold,
          textAlign: 'center',
          fontSize: 34,
          lineHeight: 1.12,
          fontWeight: 900,
          boxShadow: '0 16px 44px rgba(0,0,0,0.38)',
        }}
      >
        {ctaText}
      </div>
    </AbsoluteFill>
  );
};
