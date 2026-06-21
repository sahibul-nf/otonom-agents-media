"""Declarative recipe catalog — distinct overlay/CSS/motion per template."""

from __future__ import annotations

import html
from typing import Any

from ._factory import recipe_from_spec

_FONTS = {
    "lora": "https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,400..700;1,400..700&display=swap",
    "inter": "https://fonts.googleapis.com/css2?family=Inter:wght@500;700;900&display=swap",
    "space_mono": "https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&display=swap",
    "oswald": "https://fonts.googleapis.com/css2?family=Oswald:wght@500;700&display=swap",
    "playfair": "https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,500;0,700;1,500&display=swap",
    "bebas": "https://fonts.googleapis.com/css2?family=Bebas+Neue&display=swap",
    "dm_serif": "https://fonts.googleapis.com/css2?family=DM+Serif+Display&display=swap",
    "archivo": "https://fonts.googleapis.com/css2?family=Archivo+Black&display=swap",
    "caveat": "https://fonts.googleapis.com/css2?family=Caveat:wght@500;700&display=swap",
    "permanent": "https://fonts.googleapis.com/css2?family=Permanent+Marker&display=swap",
    "syne": "https://fonts.googleapis.com/css2?family=Syne:wght@600;800&display=swap",
    "ibm_plex": "https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&display=swap",
    "fraunces": "https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;700&display=swap",
    "outfit": "https://fonts.googleapis.com/css2?family=Outfit:wght@500;800&display=swap",
    "libre": "https://fonts.googleapis.com/css2?family=Libre+Baskerville:ital,wght@0,400;0,700;1,400&display=swap",
    "rubik": "https://fonts.googleapis.com/css2?family=Rubik:wght@500;800&display=swap",
}

_LAYER = ".template-layer{position:absolute;z-index:5;pointer-events:none}"


def _e(value: Any) -> str:
    return html.escape(str(value))


def _cap_bottom(layout) -> int:
    return 176 if layout.is_landscape else 365


def _spec(
    template_id: str,
    *,
    font: str,
    font_family: str,
    caption_style: str,
    motion: str,
    grade: str,
    video_filter: str,
    overlay_fn,
    css: str,
    motion_extra: str = "",
) -> dict[str, Any]:
    return {
        "id": template_id,
        "style": {
            "font_family": font_family,
            "google_fonts_href": _FONTS.get(font, ""),
            "caption_style": caption_style,
            "motion_preset": motion,
            "color_grade": grade,
        },
        "video_filter": video_filter,
        "overlay_builder": overlay_fn,
        "css": _LAYER + css,
        "motion_extra": motion_extra,
    }


def _spiritual_overlay(c, _t, _l):
    return f'<div class="template-layer editorial-masthead"><span class="micro-label">Reflect</span><strong>{_e(c.get("watermarkText",""))}</strong></div><div class="template-layer grain-heavy"></div>'


def _podcast_overlay(c, _t, _l):
    return f'''<div class="template-layer lower-third"><span class="micro-label">Guest</span><strong>{_e(c.get("titleHook",""))}</strong><small>{_e(c.get("watermarkText",""))}</small></div>
<div class="template-layer avatar-ring"></div><div class="template-layer social-pill">Follow for the next clip</div>'''


def _data_overlay(_c, _t, _l):
    return '<div class="template-layer metrics-panel"><div><span>Signal</span><strong>74</strong></div><div><span>Window</span><strong>Short</strong></div><div><span>Action</span><strong>Watch</strong></div></div><div class="template-layer chart-bars"><span></span><span></span><span></span><span></span></div>'


def _news_overlay(c, _t, _l):
    return f'<div class="template-layer breaking-strip">BREAKING</div><div class="template-layer map-card"><span class="micro-label">Regional brief</span><strong>{_e(c.get("sourceAttribution") or "Verified source")}</strong><div class="map-grid"><i></i><i></i><i></i><i></i></div></div><div class="template-layer ticker">Source checked · Context preserved · Review required</div>'


def _product_overlay(c, _t, _l):
    return f'<div class="template-layer logo-badge">{_e(c.get("watermarkText") or "Brand")}</div><div class="template-layer promo-card"><span class="micro-label">Creator promo</span><strong>{_e(c.get("ctaText",""))}</strong><small>Save, follow, and share</small></div><div class="template-layer chip-row"><span>NEW</span><span>SAVE 20%</span></div>'


def _warm_overlay(c, _t, _l):
    return f'<div class="template-layer magazine-masthead">THE STORY</div><div class="template-layer drop-cap">A</div><div class="template-layer handwritten-note">{_e(c.get("watermarkText",""))}</div><div class="template-layer grain-heavy"></div>'


def _play_overlay(_c, _t, _l):
    return '<div class="template-layer sticker yellow">HOOK</div><div class="template-layer sticker pink">NOW</div><div class="template-layer diagonal-tag">PLAY MODE</div>'


def _swiss_overlay(_c, _t, _l):
    return '<div class="template-layer grid-lines"></div><div class="template-layer step-badge">01</div><div class="template-layer step-badge secondary">02</div>'


def _vignelli_overlay(c, _t, _l):
    return f'<div class="template-layer portrait-headline">{_e(c.get("titleHook",""))}</div>'


def _tree_overlay(_c, _t, _l):
    return '<div class="template-layer flow-node a">Start</div><div class="template-layer flow-node b">Decide</div><div class="template-layer flow-node c">Result</div><div class="template-layer flow-arrow"></div>'


def _kinetic_overlay(_c, _t, _l):
    return '<div class="template-layer word-swap"><span class="w1">MAKE</span><span class="w2">IT</span><span class="w3">POP</span></div><div class="template-layer neon-outline"></div>'


def _saas_overlay(_c, _t, _l):
    return '<div class="template-layer ui-mock"><div class="ui-bar"></div><div class="ui-pane"></div></div><div class="template-layer cursor-dot"></div><div class="template-layer feature-pills"><span>Fast</span><span>Simple</span></div>'


def _nyt_overlay(_c, _t, _l):
    return '<div class="template-layer chart-annotation"><div class="chart-line"></div><div class="chart-dot"></div><span class="chart-label">+18%</span></div>'


def _neon_overlay(_c, _t, _l):
    return '<div class="template-layer scanlines"></div><div class="template-layer neon-frame"></div><div class="template-layer glitch-tag">CYBER</div>'


def _volt_overlay(_c, _t, _l):
    return '<div class="template-layer lime-bar"></div><div class="template-layer impact-type">VOLT</div>'


def _ember_overlay(_c, _t, _l):
    return '<div class="template-layer sunset-bloom"></div><div class="template-layer script-accent">bloom</div>'


def _align_overlay(_c, _t, _l):
    return '<div class="template-layer minimal-box-frame"></div>'


def _energy_overlay(_c, _t, _l):
    return '<div class="template-layer sticky-note yellow">more views?</div>'


def _arion_overlay(_c, _t, _l):
    return '<div class="template-layer pink-callout">say it louder</div>'


def _quint_overlay(_c, _t, _l):
    return '<div class="template-layer display-serif"><em>More</em> clarity</div>'


def _archive_overlay(_c, _t, _l):
    return '<div class="template-layer magazine-cover"><span>ARCHIVE</span><strong>Guidelines</strong></div>'


def _story_overlay(_c, _t, _l):
    return '<div class="template-layer script-hand">Creative</div>'


def _kai_overlay(_c, _t, _l):
    return '<div class="template-layer mustard-card">MUSTARD MODE</div>'


def _byline_overlay(c, _t, _l):
    return f'<div class="template-layer trust-quote">"{_e(c.get("subtitle",""))}"</div>'


def _sonnet_overlay(_c, _t, _l):
    return '<div class="template-layer botanical-accent"></div><div class="template-layer script-lessons">lessons</div>'


def _rocket_overlay(_c, _t, _l):
    return '<div class="template-layer vhs-glitch">LEVEL UP</div>'


def _grit_overlay(_c, _t, _l):
    return '<div class="template-layer training-stamp">TRAINING</div>'


def _cove_overlay(_c, _t, _l):
    return '<div class="template-layer pill-stack"><span class="pink">add captions</span><span class="cyan">in seconds</span></div>'


def _pulse_overlay(_c, _t, _l):
    return '<div class="template-layer remember-banner">REMEMBER THE CONSISTENCY</div>'


def _neon_burst_overlay(_c, _t, _l):
    return '<div class="template-layer star-burst"></div><div class="template-layer neon-future">SEIZE THE FUTURE</div>'


def _velocity_overlay(_c, _t, _l):
    return '<div class="template-layer velocity-stack"><span>BOOST</span><strong>YOUR BUSINESS</strong></div>'


def _blueprint_overlay(_c, _t, _l):
    return '<div class="template-layer graph-paper"></div><div class="template-layer blueprint-title">how to build anything</div>'


def _sketch_overlay(_c, _t, _l):
    return '<div class="template-layer post-it a">idea</div><div class="template-layer post-it b">ship</div>'


def _prism_overlay(_c, _t, _l):
    return '<div class="template-layer price-tag"><span>Pro</span><strong>$29</strong></div>'


def _chalk_overlay(_c, _t, _l):
    return '<div class="template-layer chalk-board"><span>emphasis</span></div>'


_RECIPE_SPECS: list[dict[str, Any]] = [

    _spec(
        "spiritual_reflective",
        font="lora",
        font_family='"Lora", Georgia, serif',
        caption_style="Editorial serif with dotted underline",
        motion="soft-vignette-fade",
        grade="warm cream grade",
        video_filter="contrast(1.02) saturate(0.88) brightness(0.96) sepia(0.14)",
        overlay_fn=_spiritual_overlay,
        css="#root.recipe-spiritual-reflective video{filter:contrast(1.02) saturate(.88) brightness(.96) sepia(.14)}#root.recipe-spiritual-reflective .caption-text{font-family:Lora,serif;font-style:italic;font-weight:600}#root.recipe-spiritual-reflective .caption-card{border:none;background:rgba(24,18,10,.55);border-bottom:3px dotted var(--template-accent)}.editorial-masthead{left:48px;top:52px;max-width:360px;padding:14px 18px;border-left:4px solid var(--template-accent);background:rgba(12,10,8,.55);color:#fff8eb;font-family:Lora,serif}.grain-heavy{inset:0;opacity:.22;background-image:radial-gradient(rgba(255,255,255,.18) 1px,transparent 1px);background-size:5px 5px;mix-blend-mode:overlay}",
    ),

    _spec("energy_warm_question", font="caveat", font_family='"Caveat", cursive', caption_style="Yellow sticky question", motion="note-pop", grade="warm social", video_filter="contrast(1.1) saturate(1.1) brightness(.93)", overlay_fn=_energy_overlay, css="#root.recipe-energy-warm-question .caption-text{font-family:Caveat,cursive;font-size:1.2em}.sticky-note.yellow{left:48px;top:200px;padding:18px 22px;background:#ffe566;color:#222;font-family:Caveat,cursive;font-size:34px;transform:rotate(-5deg);box-shadow:0 16px 40px rgba(0,0,0,.35);border-radius:4px 16px 16px 16px}"),

    _spec("arion_pink_callout", font="rubik", font_family='"Rubik", sans-serif', caption_style="Pink rounded callout", motion="callout-bounce", grade="pink pop", video_filter="contrast(1.12) saturate(1.2) brightness(.94)", overlay_fn=_arion_overlay, css="#root.recipe-arion-pink-callout .caption-card{background:#ff7ad1;color:#1a1020;border:none;border-radius:24px}.pink-callout{left:50%;top:45%;transform:translate(-50%,-50%);padding:22px 30px;border-radius:28px;background:#ff7ad1;color:#1a1020;font-weight:900;font-size:32px}"),

    _spec("quintessence_serif", font="dm_serif", font_family='"DM Serif Display", serif', caption_style="Display serif emphasis", motion="serif-fade", grade="editorial cream", video_filter="contrast(1.03) saturate(.86) brightness(.95) sepia(.1)", overlay_fn=_quint_overlay, css="#root.recipe-quintessence-serif .caption-text{font-family:'DM Serif Display',serif;font-size:1.1em}.display-serif{left:48px;top:180px;font-family:'DM Serif Display',serif;font-size:58px;color:#fff}.display-serif em{font-style:italic;color:var(--template-accent)}"),

    _spec("archive_magazine", font="playfair", font_family='"Playfair Display", serif', caption_style="Editorial cover", motion="cover-slide", grade="magazine muted", video_filter="contrast(1.06) saturate(.8) brightness(.88)", overlay_fn=_archive_overlay, css=".magazine-cover{left:40px;top:60px;right:40px;padding:24px;border:3px solid rgba(255,255,255,.25);font-family:'Playfair Display',serif}.magazine-cover span{letter-spacing:.28em;font-size:14px}.magazine-cover strong{display:block;margin-top:12px;font-size:48px}"),

    _spec("story_handwritten", font="caveat", font_family='"Caveat", cursive', caption_style="Handwritten accent", motion="scribble-in", grade="story warm", video_filter="contrast(1.05) saturate(1.05) brightness(.92)", overlay_fn=_story_overlay, css="#root.recipe-story-handwritten .caption-text{font-family:Caveat,cursive}.script-hand{right:52px;top:200px;font-family:Caveat,cursive;font-size:64px;color:var(--template-accent);transform:rotate(-8deg)}"),

    _spec("kai_mustard_uppercase", font="oswald", font_family='"Oswald", sans-serif', caption_style="Mustard card all-caps", motion="card-slam", grade="mustard punch", video_filter="contrast(1.14) saturate(1.05) brightness(.9)", overlay_fn=_kai_overlay, css="#root.recipe-kai-mustard-uppercase .caption-text{font-family:Oswald,sans-serif;text-transform:uppercase}.mustard-card{left:48px;top:220px;padding:20px 26px;background:#d4a017;color:#111;font-family:Oswald,sans-serif;font-size:42px;font-weight:700;letter-spacing:.08em}"),

    _spec("byline_trust_quote", font="libre", font_family='"Libre Baskerville", serif', caption_style="Centered trust quote", motion="quote-fade", grade="trust neutral", video_filter="contrast(1.04) saturate(.82) brightness(.92)", overlay_fn=_byline_overlay, css=".trust-quote{left:48px;right:48px;top:42%;text-align:center;font-family:'Libre Baskerville',serif;font-size:34px;line-height:1.35;color:rgba(255,255,255,.92)}"),

    _spec("sonnet_botanical", font="fraunces", font_family='"Fraunces", serif', caption_style="Script botanical accent", motion="botanical-drift", grade="soft botanical", video_filter="contrast(1.02) saturate(.95) brightness(.93)", overlay_fn=_sonnet_overlay, css=".botanical-accent{right:40px;top:120px;width:120px;height:120px;border-radius:50%;background:radial-gradient(circle,rgba(159,231,196,.35),transparent 70%)}.script-lessons{left:56px;bottom:280px;font-family:Caveat,cursive;font-size:52px;color:var(--template-accent)}"),

    _spec("rocket_glitch", font="bebas", font_family='"Bebas Neue", sans-serif', caption_style="VHS glitch level up", motion="vhs-glitch", grade="retro glitch", video_filter="contrast(1.2) saturate(1.25) brightness(.86)", overlay_fn=_rocket_overlay, css="#root.recipe-rocket-glitch .caption-text{font-family:'Bebas Neue',sans-serif;text-transform:uppercase}.vhs-glitch{left:40px;top:160px;font-family:'Bebas Neue',sans-serif;font-size:56px;color:#fff;text-shadow:3px 0 #f0f, -3px 0 #0ff}"),

    _spec("grit_training_stamp", font="archivo", font_family='"Archivo Black", sans-serif', caption_style="Training stamp badge", motion="stamp-slam", grade="dark grit", video_filter="contrast(1.18) saturate(.7) brightness(.78)", overlay_fn=_grit_overlay, css=".training-stamp{left:48px;top:140px;padding:14px 22px;border:4px solid #22c55e;color:#22c55e;font-family:'Archivo Black',sans-serif;font-size:28px;letter-spacing:.12em;transform:rotate(-8deg)}"),

    _spec("cove_callout_pill", font="outfit", font_family='"Outfit", sans-serif', caption_style="Pink/cyan pill stack", motion="pill-stack-rise", grade="cove bright", video_filter="contrast(1.1) saturate(1.15) brightness(.92)", overlay_fn=_cove_overlay, css=".pill-stack{left:50%;bottom:280px;transform:translateX(-50%);display:flex;flex-direction:column;gap:10px;align-items:center}.pill-stack span{padding:14px 22px;border-radius:999px;font-weight:800;font-size:22px}.pill-stack .pink{background:#ff7ad1;color:#1a1020}.pill-stack .cyan{background:#67e8f9;color:#041018}"),

    _spec("pulse_remember_overlay", font="oswald", font_family='"Oswald", sans-serif', caption_style="Red remember banner", motion="banner-punch", grade="urgent red", video_filter="contrast(1.16) saturate(1.05) brightness(.84)", overlay_fn=_pulse_overlay, css=".remember-banner{left:0;right:0;top:38%;padding:18px 24px;background:#dc2626;color:#fff;text-align:center;font-family:Oswald,sans-serif;font-size:34px;font-weight:700;letter-spacing:.06em}"),

    _spec("neon_seize_future", font="syne", font_family='"Syne", sans-serif', caption_style="Multicolor neon burst", motion="star-burst", grade="neon burst", video_filter="contrast(1.22) saturate(1.4) brightness(.86)", overlay_fn=_neon_burst_overlay, css=".star-burst{left:50%;top:35%;width:180px;height:180px;transform:translate(-50%,-50%);background:conic-gradient(from 0deg,#ff2a85,#00f3ff,#facc15,#a7f36b,#ff2a85);clip-path:polygon(50% 0%,61% 35%,98% 35%,68% 57%,79% 91%,50% 70%,21% 91%,32% 57%,2% 35%,39% 35%)}.neon-future{left:48px;right:48px;bottom:260px;text-align:center;font-family:Syne,sans-serif;font-weight:800;font-size:36px;color:#fff;text-shadow:0 0 20px #00f3ff}"),

    _spec("velocity_business_promo", font="archivo", font_family='"Archivo Black", sans-serif', caption_style="Yellow stacked business", motion="stack-rise", grade="velocity yellow", video_filter="contrast(1.15) saturate(1.12) brightness(.9)", overlay_fn=_velocity_overlay, css=".velocity-stack{left:48px;top:180px;font-family:'Archivo Black',sans-serif}.velocity-stack span{display:block;color:#facc15;font-size:28px}.velocity-stack strong{display:block;font-size:52px;color:#fff;line-height:1}"),

    _spec("blueprint_grid_paper", font="ibm_plex", font_family='"IBM Plex Mono", monospace', caption_style="Graph paper blueprint", motion="blueprint-draw", grade="blueprint cool", video_filter="contrast(1.08) saturate(.75) brightness(.9) hue-rotate(190deg)", overlay_fn=_blueprint_overlay, css="#root.recipe-blueprint-grid-paper .caption-text{font-family:'IBM Plex Mono',monospace}.graph-paper{inset:56px;background:linear-gradient(rgba(125,211,252,.12) 1px,transparent 1px),linear-gradient(90deg,rgba(125,211,252,.12) 1px,transparent 1px);background-size:24px 24px;border:1px solid rgba(125,211,252,.25)}.blueprint-title{left:64px;top:100px;font-family:'IBM Plex Mono',monospace;font-size:30px;color:#bae6fd}"),

    _spec("sketch_post_it", font="caveat", font_family='"Caveat", cursive', caption_style="Post-it sticky notes", motion="post-it-pop", grade="sketch warm", video_filter="contrast(1.06) saturate(1.02) brightness(.93)", overlay_fn=_sketch_overlay, css=".post-it{padding:16px 18px;font-family:Caveat,cursive;font-size:32px;box-shadow:0 14px 30px rgba(0,0,0,.28)}.post-it.a{left:52px;top:200px;background:#fef08a;color:#422006;transform:rotate(-6deg)}.post-it.b{right:52px;top:260px;background:#fbcfe8;color:#4a044e;transform:rotate(5deg)}"),

    _spec("prism_pro_pricing", font="outfit", font_family='"Outfit", sans-serif', caption_style="Highlighted price label", motion="price-pop", grade="prism clean", video_filter="contrast(1.1) saturate(1.08) brightness(.94)", overlay_fn=_prism_overlay, css=".price-tag{right:48px;top:160px;padding:16px 20px;border-radius:16px;background:rgba(0,0,0,.72);border:2px solid var(--template-accent);font-family:Outfit,sans-serif}.price-tag span{display:block;font-size:14px;color:rgba(255,255,255,.7)}.price-tag strong{font-size:40px;color:var(--template-accent)}"),

    _spec("chalk_word_emphasis", font="permanent", font_family='"Permanent Marker", cursive', caption_style="Chalk handwriting dark", motion="chalk-scribble", grade="chalk dark board", video_filter="contrast(1.12) saturate(.65) brightness(.78)", overlay_fn=_chalk_overlay, css="#root.recipe-chalk-word-emphasis .caption-text{font-family:'Permanent Marker',cursive;color:#f8fafc}#root.recipe-chalk-word-emphasis .caption-card{background:rgba(15,23,42,.85);border:2px dashed rgba(248,250,252,.35)}.chalk-board{left:48px;right:48px;bottom:240px;padding:20px;border-radius:8px;background:rgba(2,6,23,.75);font-family:'Permanent Marker',cursive;font-size:36px;color:#e2e8f0}"),
]

_BUILTIN_BY_ID = {spec["id"]: recipe_from_spec(spec) for spec in _RECIPE_SPECS}


def get_builtin_recipe(template_id: str):
    return _BUILTIN_BY_ID[template_id]
