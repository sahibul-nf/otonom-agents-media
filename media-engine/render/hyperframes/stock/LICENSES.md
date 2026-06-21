# Stock clip licenses

Per-template preview footage (`{template_id}.mp4`) downloaded from [Mixkit](https://mixkit.co/) under the [Mixkit License](https://mixkit.co/license/) (free commercial use).

Refresh all clips:

```bash
python3 media-engine/render/hyperframes/stock/download_stock_clips.py
```

| Template ID | Mixkit slug |
|-------------|-------------|
| `spiritual_reflective` | therapist-in-his-office-talking-to-the-camera-4834 |
| `energy_warm_question` | young-woman-recording-a-vertical-video-on-her-phone-40774 |
| `arion_pink_callout` | blonde-girl-smiling-head-on-on-the-street-4815 |
| `quintessence_serif` | portrait-of-a-woman-at-the-beach-1104 |
| `archive_magazine` | girl-reading-a-book-in-nature-4897 |
| `story_handwritten` | woman-writing-in-a-notebook-3280 |
| `kai_mustard_uppercase` | confident-young-businessman-doing-a-presentation-23117 |
| `byline_trust_quote` | woman-speaking-to-a-psychologist-6045 |
| `sonnet_botanical` | close-up-of-green-leaves-in-the-wind-1171 |
| `rocket_glitch` | programming-and-coding-new-technologies-46635 |
| `grit_training_stamp` | man-doing-weightlifting-exercises-32808 |
| `cove_callout_pill` | apps-on-a-smartphone-screen-4293 |
| `pulse_remember_overlay` | man-speaking-into-the-microphone-at-record-studio-2955 |
| `neon_seize_future` | a-woman-wearign-a-futuristic-vr-glasses-concentrates-on-the-51214 |
| `velocity_business_promo` | business-man-exposing-graphs-42648 |
| `blueprint_grid_paper` | high-tech-circuit-board-with-processor-47051 |
| `sketch_post_it` | work-team-planning-meeting-21247 |
| `prism_pro_pricing` | man-working-on-his-laptop-308 |
| `chalk_word_emphasis` | a-middle-age-man-teacher-wearing-glasses-talking-to-a-50117 |

Legacy shared pool files (`portrait_*.mp4`, `landscape_*.mp4`) are optional; run `download_stock_clips.py --legacy-pools` to refresh.

Downloaded via `download_stock_clips.py` (scrapes Mixkit page HTML for CDN URL).
