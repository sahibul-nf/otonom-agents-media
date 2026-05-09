# TechTalk Autonomous Content Creation System
## Standalone PM2 Approach (v4.0)

**Status:** ✅ Production Active  
**Last Updated:** April 13, 2026  
**Approach:** Standalone Node.js script — no agent dependency

---

## 🏗️ ARCHITECTURE OVERVIEW

```
techtalk-autonomous/
├── README.md                    # This file
├── .env                         # Environment variables (credentials)
├── .env.example                 # Template for environment variables
├── package.json                 # Node.js dependencies
├── .gitignore                   # Git ignore rules
├── config/
│   ├── techtalk_state.json      # Topic/style rotation state + weights
│   ├── posting_history.json     # Post history & performance
│   ├── reply_history.json       # Auto-reply tracking
│   └── performance_audit.json   # Topic performance analysis
└── tests/
    └── run_techtalk_dryrun.cjs  # Test runner
```

**Main scripts & PM2 config:**
```
workspace/projects/techtalk-autonomous/
├── scripts/
│   ├── techtalk-post.js         # ← MAIN POSTING SCRIPT
│   ├── techtalk-reply.js        # ← ENGAGEMENT ENGINE (auto-reply)
│   ├── techtalk-audit.js        # ← PERFORMANCE AUDITOR
│   └── techtalk-pm2.config.js   # ← PM2 ecosystem config
```

---

## 🔧 PIPELINE (v4.0)

### Content Creation Pipeline
```
PM2 cron trigger
    └─▶ techtalk-post.js
            ├─▶ Load config from environment variables
            ├─▶ Fetch market data (Binance + Yahoo Finance)
            ├─▶ Weighted topic selection (performance-based)
            ├─▶ Research (HackerNews + GitHub + Wikipedia + ArXiv)
            ├─▶ DeepSeek API (content + visual prompt)
            ├─▶ Generate image (Pollinations.ai)
            ├─▶ Parse & sanitize content
            ├─▶ Validate (length, format, safety lock)
            ├─▶ Post to Facebook (with AI-generated image)
            ├─▶ Archive content & rotate history
            └─▶ Telegram notification
```

### Engagement Engine Pipeline
```
PM2 cron trigger (every 4 hours)
    └─▶ techtalk-reply.js
            ├─▶ Check recent posts for new comments
            ├─▶ Filter (spam, links, toxic keywords)
            ├─▶ Prioritize questions
            ├─▶ Generate reply via DeepSeek
            └─▶ Post reply + track in history
```

### Performance Optimization Pipeline
```
Manual or scheduled run
    └─▶ techtalk-audit.js
            ├─▶ Analyze posting_history.json
            ├─▶ Calculate topic success rates
            ├─▶ Generate weighted recommendations
            └─▶ Update topicWeights in techtalk_state.json
```

---

## 📅 JADWAL POSTING

| PM2 Process | Halaman | Jam (WIB) | Keterangan |
|---|---|---|---|
| `techtalk-en-daily` | TechTalk Intel (EN) | 05:00, 21:00 | Content posting |
| `techtalk-id-daily` | TechTalk Intel ID | 10:00, 19:00 | Content posting |
| `techtalk-engagement` | Both | Every 4 hours | Auto-reply comments |

---

## 🛠️ CARA MANUAL RUN

### Setup (Pertama Kali)
```bash
# Install dependencies
cd workspace/projects/techtalk-autonomous
npm install

# Setup environment variables
cp .env.example .env
# Edit .env dengan credentials yang benar
```

### Content Posting
```bash
# Post ke halaman Indonesia
node scripts/techtalk-post.js --id-only

# Post ke halaman Inggris
node scripts/techtalk-post.js --en-only

# Dry-run (generate konten tapi tidak post)
node scripts/techtalk-post.js --id-only --dry-run
```

### Engagement Engine
```bash
# Check comments (dry-run)
node scripts/techtalk-reply.js --dry-run

# Actual reply to comments
node scripts/techtalk-reply.js
```

### Performance Audit
```bash
# Local analysis
node scripts/techtalk-audit.js

# With Facebook engagement fetch
node scripts/techtalk-audit.js --fetch

# Weekly report with Telegram notification
node scripts/techtalk-audit.js --weekly
```

### PM2 Management
```bash
# Start all processes
pm2 start scripts/techtalk-pm2.config.js

# Cek status
pm2 list

# Monitor log real-time
pm2 logs techtalk-id-daily
pm2 logs techtalk-engagement

# Restart semua
pm2 restart all
```

---

## 📁 DATA & STATE

- **Topic rotation**: `config/techtalk_state.json`
- **Post history**: `config/posting_history.json`
- **Content archive**: `archives/techtalk/` (every post archived)
- **Runtime log**: `~/.openclaw/logs/techtalk-standalone.log`

---

## 🔒 SAFETY

- `config/fb_safety_lock.json` — set `enabled: false` untuk disable semua FB posting
- Environment variables untuk credentials — jangan commit file `.env`
- PM2 startup terdaftar via `launchd` — otomatis restart setelah reboot Mac

---

## ✨ NEW IN V4.0

| Fitur | Deskripsi |
|---|---|
| 🔐 **Security** | API keys moved to environment variables |
| 💬 **Engagement Engine** | Auto-reply ke komentar setiap 4 jam |
| 📊 **Performance-Driven** | Weighted topic selection berdasarkan audit |
| 📦 **Auto-Archiving** | History rotation per bulan otomatis |

---

## 📜 HISTORY

| Versi | Tanggal | Keterangan |
|---|---|---|
| v1.0 | Mar 2026 | Skill-based approach, OpenClaw cron |
| v2.0 | Apr 1, 2026 | Full LLM via sessions_spawn |
| v3.0 | Apr 5, 2026 | Standalone PM2 approach |
| **v4.0** | **Apr 13, 2026** | **Security + Branding + Engagement + Optimization** |

**Alasan migrasi ke v3.0**: Agent deepseek-chat di isolated cron session tidak konsisten menginvoke skill handler — agent malah mencoba execute manual script yang diblokir security preflight. Standalone script menghilangkan ketergantungan pada agent sepenuhnya.