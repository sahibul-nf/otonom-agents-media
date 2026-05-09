#!/usr/bin/env node
/**
 * TechTalk Autonomous Poster — STANDALONE SCRIPT
 * ================================================
 * Runs completely independently of OpenClaw agents.
 * Fetches market data, generates content via DeepSeek API,
 * and posts directly to Facebook — NO agent spawning, NO exec.
 *
 * Usage:
 *   node techtalk-post.js --en-only    # Post to English (TechTalk Intel) page only
 *   node techtalk-post.js --id-only    # Post to Indonesian (TechTalk Intel ID) page only
 *   node techtalk-post.js              # Post to both pages
 *   node techtalk-post.js --dry-run    # Generate content but don't post
 */

'use strict';

const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

// Watermark module - re-enabled for v5.0
let watermarkModule;
try {
  watermarkModule = require(path.join(__dirname, '../lib/watermark.js'));
} catch (e) {
  console.log('⚠️ Watermark module not available:', e.message);
}

// ──────────────────────────────────────────────────────────────
// CONFIGURATION
// ──────────────────────────────────────────────────────────────

// Load environment variables from .env file if exists
try {
  const envPath = path.join(__dirname, '../.env');
  if (require('fs').existsSync(envPath)) {
    require('dotenv').config({ path: envPath });
  }
} catch (e) {
  // dotenv not installed, proceed with process.env
}

const CONFIG = {
  deepseekApiKey: process.env.DEEPSEEK_API_KEY || '',
  deepseekBaseUrl: process.env.DEEPSEEK_BASE_URL || 'https://api.deepseek.com/v1',
  deepseekModel: process.env.DEEPSEEK_MODEL || 'deepseek-chat',
  fbPagesConfig: path.join(__dirname, '../config/fb_pages.json'),
  safetyLock: path.join(__dirname, '../config/fb_safety_lock.json'),
  postingHistory: process.env.POSTING_HISTORY_PATH || path.join(__dirname, '../config/posting_history.json'),
  stateFile: process.env.STATE_FILE_PATH || path.join(__dirname, '../config/techtalk_state.json'),
  fbScript: path.join(__dirname, './fb-post.js'),
  archiveDir: process.env.ARCHIVE_DIR_PATH || path.join(__dirname, '../archives/techtalk'),
  logFile: process.env.LOG_FILE_PATH || path.join(__dirname, '../logs/techtalk-standalone.log'),
  // Telegram
  telegramBotToken: process.env.TELEGRAM_BOT_TOKEN || '',
  telegramChatId: process.env.TELEGRAM_CHAT_ID || '',
  telegramThreadId: process.env.TELEGRAM_THREAD_ID || '',
};

// Validate required environment variables
function validateConfig() {
  const required = [
    { key: 'deepseekApiKey', name: 'DEEPSEEK_API_KEY' },
    { key: 'telegramBotToken', name: 'TELEGRAM_BOT_TOKEN' },
    { key: 'telegramChatId', name: 'TELEGRAM_CHAT_ID' },
  ];
  
  const missing = required.filter(r => !CONFIG[r.key]);
  if (missing.length > 0) {
    console.error('❌ Missing required environment variables:');
    missing.forEach(m => console.error(`   - ${m.name}`));
    console.error('\nPlease create .env file based on .env.example');
    process.exit(1);
  }
}

// Topic rotation pool
const TOPICS = [
  'Cryptocurrency Markets', 'Blockchain Engineering', 'AI and Machine Learning',
  'Cybersecurity', 'Cloud Computing', 'Biotechnology & Life Sciences',
  'Web3 and Decentralization', 'Semiconductors and Hardware', 'FinTech Innovation',
  'Edge Computing', '5G and Connectivity', 'Quantum Computing',
  'AR/VR and Metaverse', 'Green Technology', 'HealthTech Advances',
  'Autonomous Systems', 'Digital Transformation',
  'Finance Tips & Tricks', 'Tech Productivity Hacks', 'Personal Finance Automation',
  'Career Growth in Tech', 'Space Tech & Satellites', 'Robotics & Automation',
  'DevSecOps', 'Platform Engineering',
];

const STYLES = [
  { id: 'tech-insights', name: 'Tech Insights', desc: 'Technology-focused insights and innovation spotlight', researchMode: 'news' },
  { id: 'market-analysis', name: 'Market Analysis', desc: 'Data-driven market analysis with metrics and trends', researchMode: 'news' },
  { id: 'educational', name: 'Educational', desc: 'Explanatory content with best practices', researchMode: 'fundamental' },
  { id: 'industry-news', name: 'Industry News', desc: 'Industry developments and business context', researchMode: 'news' },
  { id: 'trend-spotlight', name: 'Trend Spotlight', desc: 'Focus on emerging trends and future outlook', researchMode: 'news' },
  { id: 'advanced-deep-dive', name: 'Advanced Deep Dive', desc: 'Technical deep dive into architecture and principles', researchMode: 'deep' },
  { id: 'pro-tips', name: 'Pro Tips', desc: 'Actionable tips and tricks for engineers and investors', researchMode: 'news' },
  { id: 'future-outlook', name: 'Future Outlook', desc: 'Forward-looking perspective on technology evolution', researchMode: 'news' },
  { id: 'contrarian-view', name: 'Contrarian View', desc: 'Critical analysis challenging popular tech narratives', researchMode: 'deep' },
];

// Maps topic → GitHub search keywords for github-ai-trends-style queries
const TOPIC_GITHUB_KEYWORDS = {
  'AI and Machine Learning': ['llm', 'ai-agent', 'machine-learning'],
  'Blockchain Engineering': ['blockchain', 'web3', 'ethereum'],
  'Cryptocurrency Markets': ['defi', 'crypto', 'bitcoin'],
  'Cybersecurity': ['security', 'cryptography', 'zero-trust'],
  'Cloud Computing': ['cloud-native', 'kubernetes', 'serverless'],
  'Biotechnology & Life Sciences': ['bioinformatics', 'genomics', 'computational-biology'],
  'Web3 and Decentralization': ['web3', 'ipfs', 'decentralized'],
  'Semiconductors and Hardware': ['fpga', 'risc-v', 'chip-design'],
  'FinTech Innovation': ['fintech', 'open-banking', 'payments'],
  'Edge Computing': ['edge-computing', 'iot', 'embedded'],
  '5G and Connectivity': ['5g', 'network', 'wireless'],
  'Quantum Computing': ['quantum', 'qiskit', 'quantum-computing'],
  'AR/VR and Metaverse': ['vr', 'ar', 'metaverse', 'webxr'],
  'Green Technology': ['sustainability', 'renewable-energy', 'carbon'],
  'HealthTech Advances': ['health', 'medical-imaging', 'digital-health'],
  'Autonomous Systems': ['robotics', 'autonomous', 'self-driving'],
  'Digital Transformation': ['devops', 'platform-engineering', 'microservices'],
  'Finance Tips & Tricks': ['finance', 'investing', 'money-management'],
  'Tech Productivity Hacks': ['productivity', 'automation', 'tools'],
  'Personal Finance Automation': ['personal-finance', 'automation', 'fintech'],
  'Career Growth in Tech': ['career', 'engineering-management', 'soft-skills'],
  'Space Tech & Satellites': ['space', 'satellite', 'aerospace'],
  'Robotics & Automation': ['robotics', 'automation', 'ros'],
  'DevSecOps': ['devsecops', 'security-as-code', 'shifting-left'],
  'Platform Engineering': ['platform-engineering', 'infrastructure-as-code'],
};

// Maps topic → ArXiv title-search keywords (ordered by specificity)
// ArXiv API: ti:keyword searches paper TITLES only — most precise method
const TOPIC_ARXIV_QUERIES = {
  'AI and Machine Learning':        ['large language model', 'LLM agent', 'transformer reasoning', 'neural network'],
  'Blockchain Engineering':          ['blockchain', 'smart contract', 'distributed ledger', 'consensus protocol'],
  'Cryptocurrency Markets':          ['DeFi', 'cryptocurrency', 'decentralized finance', 'blockchain finance'],
  'Cybersecurity':                   ['adversarial attack', 'intrusion detection', 'zero-trust', 'malware detection'],
  'Cloud Computing':                 ['cloud computing', 'serverless', 'kubernetes', 'microservices deployment'],
  'Biotechnology & Life Sciences':   ['drug discovery', 'protein structure', 'genomics', 'CRISPR', 'computational biology'],
  'Web3 and Decentralization':       ['decentralized', 'peer-to-peer network', 'blockchain protocol'],
  'Semiconductors and Hardware':     ['chip architecture', 'VLSI', 'neural processing unit', 'processor design'],
  'FinTech Innovation':              ['financial machine learning', 'algorithmic trading', 'payment system'],
  'Edge Computing':                  ['edge computing', 'IoT inference', 'federated learning edge'],
  '5G and Connectivity':             ['5G network', 'millimeter wave', 'network slicing'],
  'Quantum Computing':               ['quantum computing', 'quantum algorithm', 'qubit error correction'],
  'AR/VR and Metaverse':             ['augmented reality', 'virtual reality rendering', 'neural rendering'],
  'Green Technology':                ['renewable energy optimization', 'carbon emission', 'energy efficiency'],
  'HealthTech Advances':             ['medical imaging', 'clinical AI', 'disease diagnosis deep learning'],
  'Autonomous Systems':              ['autonomous driving', 'reinforcement learning robotics', 'path planning'],
  'Digital Transformation':          ['software engineering', 'DevOps', 'platform engineering'],
  'Finance Tips & Tricks':           ['financial engineering', 'quantitative finance', 'behavioral finance'],
  'Tech Productivity Hacks':         ['software engineering productivity', 'developer tools', 'automation workflow'],
  'Personal Finance Automation':     ['algorithmic trading', 'personal finance technology', 'automated budgeting'],
  'Career Growth in Tech':           ['software engineering career', 'leadership in technology', 'technical career path'],
  'Space Tech & Satellites':         ['satellite communication', 'space exploration technology', 'orbital mechanics'],
  'Robotics & Automation':           ['robotics control', 'human-robot interaction', 'autonomous robots'],
  'DevSecOps':                       ['DevSecOps integration', 'software supply chain security', 'automated security testing'],
  'Platform Engineering':            ['developer platform', 'internal developer portal', 'infrastructure abstraction'],
};



// ──────────────────────────────────────────────────────────────
// LOGGING
// ──────────────────────────────────────────────────────────────

function log(msg) {
  const ts = new Date().toISOString();
  const line = `[${ts}] ${msg}`;
  console.log(line);
  try {
    fs.appendFileSync(CONFIG.logFile, line + '\n');
  } catch (e) { /* ignore log write failures */ }
}

// ──────────────────────────────────────────────────────────────
// TELEGRAM NOTIFICATION
// ──────────────────────────────────────────────────────────────

async function sendTelegram(text) {
  try {
    const url = `https://api.telegram.org/bot${CONFIG.telegramBotToken}/sendMessage`;
    const payload = {
      chat_id: CONFIG.telegramChatId,
      text,
      parse_mode: 'HTML',
      disable_web_page_preview: true,
    };
    // Send to specific topic/thread if configured
    if (CONFIG.telegramThreadId) {
      payload.message_thread_id = CONFIG.telegramThreadId;
    }
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.text();
      log(`⚠️ Telegram send failed: ${err}`);
    } else {
      log('📨 Telegram notification sent');
    }
  } catch (e) {
    log(`⚠️ Telegram error (non-fatal): ${e.message}`);
  }
}

// ──────────────────────────────────────────────────────────────
// PARSE ARGS
// ──────────────────────────────────────────────────────────────

const args = process.argv.slice(2);
const enOnly = args.includes('--en-only');
const idOnly = args.includes('--id-only');
const dryRun = args.includes('--dry-run');

// ──────────────────────────────────────────────────────────────
// SAFETY LOCK CHECK
// ──────────────────────────────────────────────────────────────

function checkSafetyLock() {
  if (!fs.existsSync(CONFIG.safetyLock)) return; // no lock = allowed
  const lock = JSON.parse(fs.readFileSync(CONFIG.safetyLock, 'utf8'));
  if (lock.enabled === false) {
    throw new Error(`SAFETY LOCK ENGAGED: ${lock.reason}`);
  }
}

// ──────────────────────────────────────────────────────────────
// STATE MANAGEMENT
// ──────────────────────────────────────────────────────────────

function readState() {
  if (!fs.existsSync(CONFIG.stateFile)) return { usedTopics: [], usedStyles: [], topicAngles: {} };
  try {
    const state = JSON.parse(fs.readFileSync(CONFIG.stateFile, 'utf8'));
    if (!state.topicAngles) state.topicAngles = {};
    return state;
  }
  catch (e) { return { usedTopics: [], usedStyles: [], topicAngles: {} }; }
}

function writeState(state) {
  fs.mkdirSync(path.dirname(CONFIG.stateFile), { recursive: true });
  fs.writeFileSync(CONFIG.stateFile, JSON.stringify(state, null, 2));
}

function pickTopic(state) {
  // Avoid last 10 topics to ensure high variety
  const recent = (state.usedTopics || []).slice(-10);
  const available = TOPICS.filter(t => !recent.includes(t));
  
  if (available.length === 0) {
    return TOPICS[0];
  }
  
  // Use weighted selection if weights available from audit
  const weights = state.topicWeights || {};
  const weightedTopics = available.map(topic => ({
    topic,
    weight: weights[topic]?.normalizedWeight || (1 / available.length),
  }));
  
  // Weighted random selection
  const totalWeight = weightedTopics.reduce((sum, t) => sum + t.weight, 0);
  let random = Math.random() * totalWeight;
  
  for (const wt of weightedTopics) {
    random -= wt.weight;
    if (random <= 0) {
      return wt.topic;
    }
  }
  
  // Fallback to random
  return available[Math.floor(Math.random() * available.length)];
}

function pickStyle(topic, state) {
  // Avoid last 4 styles
  const recent = (state.usedStyles || []).slice(-4);
  const available = STYLES.filter(s => !recent.includes(s.id));
  
  if (available.length > 0) {
    const idx = Math.floor(Math.random() * available.length);
    return available[idx];
  }
  return STYLES[0];
}

// ──────────────────────────────────────────────────────────────
// MARKET DATA
// ──────────────────────────────────────────────────────────────

async function fetchMarketData() {
  const data = { crypto: {}, stocks: {}, sources: [] };

  // Crypto — Binance public API
  try {
    const r = await fetch('https://api.binance.com/api/v3/ticker/price?symbols=["BTCUSDT","ETHUSDT","SOLUSDT"]');
    if (r.ok) {
      const prices = await r.json();
      prices.forEach(p => { data.crypto[p.symbol.replace('USDT', '')] = parseFloat(p.price); });
      data.sources.push('binance-api');
      log(`   Crypto fetched: BTC $${Math.round(data.crypto.BTC)}, ETH $${Math.round(data.crypto.ETH)}`);
    }
  } catch (e) {
    data.crypto = { BTC: 66500, ETH: 2050, SOL: 80 };
    data.sources.push('crypto-fallback');
    log(`   Crypto fallback used: ${e.message}`);
  }

  // Stock — Yahoo Finance
  try {
    const r = await fetch('https://query1.finance.yahoo.com/v8/finance/chart/NVDA');
    if (r.ok) {
      const j = await r.json();
      data.stocks.NVDA = j.chart.result[0].meta.regularMarketPrice;
      data.sources.push('yahoo-finance');
      log(`   Stock fetched: NVDA $${data.stocks.NVDA}`);
    }
  } catch (e) {
    data.stocks.NVDA = 177.39;
    data.sources.push('stock-fallback');
    log(`   Stock fallback used: ${e.message}`);
  }

  return data;
}

// ──────────────────────────────────────────────────────────────
// RESEARCH ENGINE
// Replicates the data sources used by installed OpenClaw skills:
//   - HackerNews Algolia (like openclaw-web-search for tech)
//   - GitHub Search API (same as github-ai-trends skill)
//   - Wikipedia REST API (for fundamental/educational context)
// All are free, no API key required
// ──────────────────────────────────────────────────────────────

async function fetchHackerNews(topic, mode) {
  const results = [];
  try {
    // For news mode: search last 48h. For others: broader search.
    const cutoff = mode === 'news'
      ? Math.floor((Date.now() - 48 * 3600 * 1000) / 1000)
      : Math.floor((Date.now() - 30 * 24 * 3600 * 1000) / 1000);

    const query = encodeURIComponent(topic);
    const tags = mode === 'news' ? 'story' : 'story,ask_hn';
    const url = `https://hn.algolia.com/api/v1/search?query=${query}&tags=${tags}&numericFilters=created_at_i>${cutoff}&hitsPerPage=5`;

    const r = await fetch(url, { signal: AbortSignal.timeout(8000) });
    if (!r.ok) return results;

    const json = await r.json();
    for (const hit of (json.hits || []).slice(0, 5)) {
      const title = hit.title || hit.story_title;
      if (title && title.length > 10) {
        results.push(`• [HN] ${title}${hit.points ? ` (${hit.points} pts)` : ''}`);
      }
    }
    log(`   HackerNews: fetched ${results.length} items for "${topic}"`);
  } catch (e) {
    log(`   HackerNews: skipped (${e.message})`);
  }
  return results;
}

async function fetchGitHubTrending(topic) {
  // Same logic as github-ai-trends skill's fetch_trends.py
  const results = [];
  const keywords = TOPIC_GITHUB_KEYWORDS[topic] || [topic.toLowerCase().split(' ')[0]];
  try {
    const since = new Date(Date.now() - 7 * 24 * 3600 * 1000).toISOString().split('T')[0];
    const kw = keywords[0];
    const q = encodeURIComponent(`${kw} pushed:>=${since} stars:>=50`);
    const url = `https://api.github.com/search/repositories?q=${q}&sort=stars&order=desc&per_page=3`;

    const r = await fetch(url, {
      headers: { 'Accept': 'application/vnd.github+json', 'User-Agent': 'techtalk-poster' },
      signal: AbortSignal.timeout(8000),
    });
    if (!r.ok) return results;

    const json = await r.json();
    for (const repo of (json.items || []).slice(0, 3)) {
      const stars = repo.stargazers_count >= 1000
        ? `${(repo.stargazers_count / 1000).toFixed(1)}k`
        : repo.stargazers_count;
      const desc = repo.description ? `: ${repo.description.slice(0, 80)}` : '';
      results.push(`• [GitHub ⭐${stars}] ${repo.full_name}${desc}`);
    }
    log(`   GitHub Trending: fetched ${results.length} repos for "${topic}"`);
  } catch (e) {
    log(`   GitHub Trending: skipped (${e.message})`);
  }
  return results;
}

async function fetchWikipediaSummary(topic) {
  const results = [];
  try {
    const searchTerm = encodeURIComponent(topic.split('&')[0].trim());
    const url = `https://en.wikipedia.org/api/rest_v1/page/summary/${searchTerm}`;
    const r = await fetch(url, { signal: AbortSignal.timeout(6000) });
    if (!r.ok) return results;

    const json = await r.json();
    if (json.extract && json.extract.length > 50) {
      // Take first 2 meaningful sentences
      const sentences = json.extract.split('. ').slice(0, 2).join('. ');
      results.push(`• [Wikipedia] ${sentences}.`);
      log(`   Wikipedia: fetched summary for "${topic}"`);
    }
  } catch (e) {
    log(`   Wikipedia: skipped (${e.message})`);
  }
  return results;
}

async function fetchArXiv(topic) {
  // ArXiv Atom API — free, no key required
  // Uses ti: (title) field search sequentially through topic keywords
  // for high-precision, relevant results
  const results = [];
  const keywords = TOPIC_ARXIV_QUERIES[topic];
  if (!keywords || keywords.length === 0) {
    log(`   ArXiv: no keywords defined for "${topic}", skipping`);
    return results;
  }

  try {
    for (const kw of keywords) {
      if (results.length >= 2) break; // Stop once we have 2 relevant papers

      const url = `https://export.arxiv.org/api/query?search_query=ti:${encodeURIComponent(kw)}&sortBy=submittedDate&sortOrder=descending&max_results=2`;
      const r = await fetch(url, {
        headers: { 'User-Agent': 'techtalk-poster/3.0' },
        signal: AbortSignal.timeout(8000),
      });
      if (!r.ok) continue;

      const xml = await r.text();
      const titleMatches = xml.matchAll(/<entry>[\s\S]*?<title>(.*?)<\/title>/g);
      for (const match of titleMatches) {
        const title = match[1].replace(/\s+/g, ' ').trim();
        if (title && title.length > 15) {
          results.push(`• [ArXiv] ${title}`);
        }
        if (results.length >= 2) break;
      }
    }

    log(`   ArXiv: fetched ${results.length} papers for "${topic}"`);
  } catch (e) {
    log(`   ArXiv: skipped (${e.message})`);
  }
  return results;
}

async function fetchProductHunt() {
  const results = [];
  try {
    log('   ProductHunt: Fetching today\'s trending products...');
    // Public scrape of the today's launches
    const r = await fetch('https://www.producthunt.com/', {
      headers: { 'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36' },
      signal: AbortSignal.timeout(10000)
    });
    if (!r.ok) return results;

    const html = await r.text();
    // Simplified regex to catch product names from the JSON-LD or meta tags if possible
    // or just look for the title patterns
    const matches = html.matchAll(/"name":"([^"]+)"/g);
    const seen = new Set();
    for (const match of matches) {
      const name = match[1];
      if (name.length > 3 && name.length < 40 && !seen.has(name) && !['Product Hunt', 'Home'].includes(name)) {
        results.push(`• [ProductHunt] ${name} - trending today`);
        seen.add(name);
      }
      if (results.length >= 3) break;
    }
    log(`   ProductHunt: fetched ${results.length} trending items`);
  } catch (e) {
    log(`   ProductHunt: skipped (${e.message})`);
  }
  return results;
}

/**
 * Context-aware research engine:
 * - 'news':        HN (48h) + GitHub trending             → for News/Trend/Market styles
 * - 'fundamental': Wikipedia + ArXiv + HN broad + GitHub  → for Educational style
 * - 'deep':        All sources (HN + Wiki + ArXiv + GH)   → for Advanced Deep Dive
 */
async function researchTopic(topic, style) {
  const mode = style.researchMode || 'news';
  log(`🔍 Researching: "${topic}" [mode: ${mode}]...`);

  const allItems = [];
  const sources = [];

  if (mode === 'news' || mode === 'deep') {
    const hn = await fetchHackerNews(topic, 'news');
    allItems.push(...hn);
    if (hn.length > 0) sources.push('HackerNews');
  }

  if (mode === 'fundamental' || mode === 'deep') {
    const wiki = await fetchWikipediaSummary(topic);
    allItems.push(...wiki);
    if (wiki.length > 0) sources.push('Wikipedia');

    // ArXiv: academic papers for scientific/technical depth
    const arxiv = await fetchArXiv(topic);
    allItems.push(...arxiv);
    if (arxiv.length > 0) sources.push('ArXiv');

    // Broader HN discussions (Ask HN, Show HN) for community perspective
    const hnBroad = await fetchHackerNews(topic, 'broad');
    allItems.push(...hnBroad);
    if (hnBroad.length > 0 && !sources.includes('HackerNews')) sources.push('HackerNews');
  }

  // GitHub always — shows what engineers are actually building
  const gh = await fetchGitHubTrending(topic);
  allItems.push(...gh);
  if (gh.length > 0) sources.push('GitHub');

  // Product Hunt for specific innovation/market topics
  if (mode === 'news' || mode === 'deep' || topic.includes('Innovation') || topic.includes('Trends')) {
    const ph = await fetchProductHunt();
    allItems.push(...ph);
    if (ph.length > 0) sources.push('ProductHunt');
  }

  if (allItems.length === 0) {
    log(`   No research data found — proceeding with LLM knowledge only`);
    return { items: [], sources: [] };
  }

  log(`   ✅ Research complete: ${allItems.length} items from [${sources.join(', ')}]`);
  return { items: allItems, sources };
}

// ──────────────────────────────────────────────────────────────
// CONTENT GENERATION — Direct DeepSeek API call
// ──────────────────────────────────────────────────────────────

function buildPrompt(topic, style, marketData, researchContext, lastHooks = [], visualContext = null) {
  const date = new Date().toLocaleDateString('en-US', {
    weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
  });

  const isFinancial = topic.includes('Cryptocurrency') || topic.includes('Web3') || topic.includes('FinTech') || topic.includes('Finance');
  const marketLine = isFinancial
    ? `MARKET DATA (mention naturally): BTC $${Math.round(marketData.crypto.BTC).toLocaleString()}, ETH $${Math.round(marketData.crypto.ETH).toLocaleString()}, NVDA $${marketData.stocks.NVDA}`
    : `CONTEXT (keep in mind): BTC $${Math.round(marketData.crypto.BTC).toLocaleString()}, NVDA $${marketData.stocks.NVDA}`;

  let researchBlock = '';
  if (researchContext && researchContext.items.length > 0) {
    researchBlock = `
RESEARCH DATA FOR THIS POST:
${researchContext.items.join('\n')}

Instruction: Weave these facts into the narrative. Avoid generic "top tips" style.`;
  }

  let diversificationBlock = '';
  if (lastHooks.length > 0) {
    diversificationBlock = `
RECENT ANGLES (DO NOT REPEAT THESE):
${lastHooks.map(h => `- ${h}`).join('\n')}

Instruction: Take a fresh perspective. If the recent posts were about ${lastHooks[0].slice(0, 30)}..., try something contrasting or focusing on a different sub-layer of the topic.`;
  }

  let visualInstruction = '';
  if (visualContext) {
    visualInstruction = `
## 🎨 VISUAL TASK (STRICT):
Decide the visual VIBE based on these rules:
- Use 'TECHNICAL' or 'BLUEPRINT' if it's a fundamental/deep-dive topic.
- Use 'CINEMATIC' or 'CYBERPUNK' if it's a news/market topic.
- Use 'TECHNICAL' or 'BLUEPRINT' for educational/tips topics.
- Use 'AVATAR' if you feel the persona should present this info directly.
- PERSONALITY: ${visualContext.useAvatar ? 'Force use of AVATAR vibe for this specific post.' : 'Focus on a striking technical object or conceptual landscape.'}
- PERSPECTIVE: ${visualContext.perspective}

Output exactly in this format within the ===VISUAL=== block:
VIBE: [CINEMATIC|TECHNICAL|AVATAR|CYBERPUNK|BLUEPRINT]
PROMPT: [1-sentence English descriptive prompt for DALL-E/Midjourney style]`;
  }

  return `You are TechTalk Intel, a world-class tech analyst and influencer.

## 🎨 VISUAL TASK (STRICT):
Decide the visual VIBE based on these rules:
- Use 'TECHNICAL' or 'BLUEPRINT' if it's a fundamental/deep-dive topic.
- Use 'CINEMATIC' or 'CYBERPUNK' if it's a news/market topic.
- Use 'TECHNICAL' or 'BLUEPRINT' for educational/tips topics.
- Use 'AVATAR' if you feel the persona should present this info directly.
- PERSONALITY: ${visualContext ? (visualContext.useAvatar ? 'Force use of AVATAR vibe for this specific post.' : 'Focus on a striking technical object or conceptual landscape.') : 'Focus on tech aesthetics.'}
- PERSPECTIVE: ${visualContext ? visualContext.perspective : 'Cinematic'}

Output exactly in this format within the ===VISUAL=== block:
VIBE: [CINEMATIC|TECHNICAL|AVATAR|CYBERPUNK|BLUEPRINT]
PROMPT: [1-sentence English descriptive prompt for DALL-E/Midjourney style]

RULES (STRICT):
1. HOOK: Start with a 1-sentence thought-provoking hook (max 120 chars). No generic "Hello world".
2. FLOW: Use short paragraphs (2-3 sentences each). Total 3-4 paragraphs.
3. TONE: Professional but "insider" tech knowledge. 
4. EMOJIS: Max 2 relevant tech/minimalist emojis (🚀, 🏗️, ⚡, 🧠). No emotional emojis like 😭 or 😂.
5. CTA: End the post text with ONE engaging question for the audience.
6. HASHTAGS: At the ABSOLUTE END (after the CTA), put 4-5 hashtags. Start with #TechTalkIntel.
7. LANGUAGE (INDONESIAN): Use a "High-Level Tech Analyst" persona. Use professional but modern Indonesian. 
   - Rule: NEVER use direct robotic translations like "Buatan investor" for "For investors". 
   - Use: "Buat para investor...", "Di mata investor...", "Kalau lo liat dari sisi infra...", "Kuncinya ada di..."
   - Slang: Keep it natural (cuan, gas, infra, fundamental, dev). Avoid overusing "Ngabers" if the topic is serious.

OUTPUT FORMAT:
===VISUAL===
VIBE: [Vibe here]
PROMPT: [Prompt here]
===END VISUAL===

===ENGLISH===
[Post text]
[Question?]

#TechTalkIntel #hashtag1 #hashtag2...
===END ENGLISH===

===INDONESIAN===
[Post text]
[Pertanyaan?]

#TechTalkIntel #hashtag1 #hashtag2...
===END INDONESIAN===

---
TASK: Write a viral, high-authority Facebook post about "${topic}".
DATE: ${date}
STYLE: ${style.name} (${style.desc})
${marketLine}
${researchBlock}
${diversificationBlock}`;
}

async function generateContent(topic, style, marketData, researchContext, lastHooks = [], visualContext = null) {
  log(`   Calling DeepSeek API (Consolidated) for topic: ${topic}`);

  const prompt = buildPrompt(topic, style, marketData, researchContext, lastHooks, visualContext);

  const res = await fetch(`${CONFIG.deepseekBaseUrl}/chat/completions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${CONFIG.deepseekApiKey}`,
    },
    body: JSON.stringify({
      model: CONFIG.deepseekModel,
      messages: [{ role: 'user', content: prompt }],
      max_tokens: 1500,
      temperature: 0.75,
    }),
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`DeepSeek API error ${res.status}: ${err}`);
  }

  const json = await res.json();
  const raw = json.choices?.[0]?.message?.content || '';
  log(`   DeepSeek response received: ${raw.length} chars (Saved 1 API call)`);
  return raw;
}

/**
 * PHASE 5: VISUAL GENERATION — Zero-cost via Pollinations.ai
 * Generates a contextual image based on the post content.
 */

const VISUAL_STYLES = {
  CINEMATIC: "cinematic 3d render, futuristic high-tech aesthetic, neon accents, volumetric lighting, dark atmosphere, highly detailed, 8k resolution, Unreal Engine 5 style",
  TECHNICAL: "clean technical drawing style, professional minimalist infographic, blue and white color palette, diagrams, schematic aesthetic, paper texture background, high detail, scientific paper look",
  AVATAR: "futuristic cyber-analyst character (TechTalk Intel avatar), sleek white and blue smart suit, floating holographic screens, high-tech glasses reflecting code, professional posture, portrait shot, cinematic lighting, ultra-realistic, 8k",
  CYBERPUNK: "vibrant cyberpunk street aesthetics, glitch effects, deep purples and oranges, high contrast, rainy atmosphere, busy tech environment, high energy",
  BLUEPRINT: "engineering blueprint style, white lines on blue background, technical measurements, grid patterns, highly structured, industrial design look",
};

const PERSPECTIVES = ['Macro close-up', 'Wide-angle landscape', 'Aerial top-down', 'Isometric 30-degree', 'Portrait chest-up'];

async function fetchImage(imagePrompt, filename, vibe = 'CINEMATIC', attempts = 3) {
  const seed = Math.floor(Math.random() * 1000000);
  const styleSuffix = VISUAL_STYLES[vibe] || VISUAL_STYLES.CINEMATIC;
  const fullPrompt = encodeURIComponent(`${imagePrompt}, ${styleSuffix}`);
  const url = `https://image.pollinations.ai/prompt/${fullPrompt}?nologo=true&width=1024&height=768&seed=${seed}`;

  for (let i = 1; i <= attempts; i++) {
    try {
      log(`   Downloading image from Pollinations.ai (attempt ${i}/${attempts})...`);
      // Increased timeout to 60s
      const res = await fetch(url, { signal: AbortSignal.timeout(60000) });
      
      if (!res.ok) {
        if (res.status === 429 && i < attempts) {
          log(`   ⚠️ Rate limited (429), waiting 5s before retry...`);
          await new Promise(r => setTimeout(r, 5000));
          continue;
        }
        throw new Error(`Image API returned ${res.status}`);
      }

      const buffer = Buffer.from(await res.arrayBuffer());

      // Basic size validation (< 10MB for FB)
      const sizeMB = buffer.length / (1024 * 1024);
      if (sizeMB > 9) throw new Error(`Generated image too large: ${sizeMB.toFixed(2)} MB`);

      const imgPath = path.join(path.dirname(CONFIG.archiveDir), 'images', filename);
      fs.mkdirSync(path.dirname(imgPath), { recursive: true });
      fs.writeFileSync(imgPath, buffer);

      log(`   ✅ Visual saved: ${path.basename(imgPath)} (${sizeMB.toFixed(2)} MB)`);
      return imgPath;
    } catch (e) {
      if (i < attempts) {
        log(`   ⚠️ Attempt ${i} failed: ${e.message}. Retrying...`);
        // Small delay between retries
        await new Promise(r => setTimeout(r, 2000));
        continue;
      }
      log(`   ❌ Image generation failed after ${attempts} attempts: ${e.message} — falling back to text-only`);
      return null;
    }
  }
}

async function processVisual(rawLLMResponse, topic) {
  try {
    const visualBlock = extractSection(rawLLMResponse, 'VISUAL');
    if (!visualBlock) throw new Error('No VISUAL block found in content');

    const vibeMatch = visualBlock.match(/VIBE:\s*(CINEMATIC|TECHNICAL|AVATAR|CYBERPUNK|BLUEPRINT)/i);
    const promptMatch = visualBlock.match(/PROMPT:\s*(.*)/i);

    const vibe = vibeMatch ? vibeMatch[1].toUpperCase() : 'CINEMATIC';
    const imagePrompt = promptMatch ? promptMatch[1].trim().replace(/"/g, '') : topic;

    log(`   Parsed Visual: Vibe: ${vibe} | Prompt: "${imagePrompt.slice(0, 50)}..."`);

    const ts = new Date().toISOString().replace(/[:.]/g, '-');
    const filename = `techtalk_${ts}.jpg`;

    // Generate raw image
    const rawImagePath = await fetchImage(imagePrompt, filename, vibe);
    
    // Apply Watermark if raw image successful
    if (rawImagePath && watermarkModule) {
      const watermarkedPath = rawImagePath.replace('.jpg', '_wm.jpg');
      log(`   Applying brand watermark to ${path.basename(rawImagePath)}...`);
      await watermarkModule.addWatermark(rawImagePath, watermarkedPath);
      return watermarkedPath;
    }
    
    return rawImagePath;
  } catch (e) {
    log(`   ⚠️ Visual parsing failed, attempting fallback: ${e.message}`);
    // Fallback: use topic and cinematic vibe
    const ts = new Date().toISOString().replace(/[:.]/g, '-');
    const rawPath = await fetchImage(topic, `techtalk_fallback_${ts}.jpg`, 'CINEMATIC');
    
    if (rawPath && watermarkModule) {
      const wmPath = rawPath.replace('.jpg', '_wm.jpg');
      await watermarkModule.addWatermark(rawPath, wmPath);
      return wmPath;
    }
    return rawPath;
  }
}


// ──────────────────────────────────────────────────────────────
// CONTENT PARSING & SANITISATION
// ──────────────────────────────────────────────────────────────

function sanitizeForFacebook(text) {
  return text
    .replace(/\\n/g, '\n')           // unescape literal \n from LLM
    .replace(/\\t/g, '\t')           // unescape literal \t
    .replace(/\*\*(.+?)\*\*/g, '$1') // strip markdown bold
    .replace(/\*(.+?)\*/g, '$1')     // strip markdown italic
    .replace(/\n{3,}/g, '\n\n')      // collapse excess blank lines
    .trim();
}

function extractSection(content, lang) {
  const startMark = `===${lang}===`;
  const endMark = `===END ${lang}===`;

  // Try compact markers first, then spaced variants
  let startIdx = content.indexOf(startMark);
  let endIdx = content.indexOf(endMark);

  if (startIdx === -1) startIdx = content.indexOf(`=== ${lang} ===`);
  if (endIdx === -1) endIdx = content.indexOf(`=== END ${lang} ===`);

  if (startIdx !== -1 && endIdx !== -1) {
    const rawStart = startIdx + (content.includes(startMark) ? startMark.length : `=== ${lang} ===`.length);
    return sanitizeForFacebook(content.substring(rawStart, endIdx));
  }

  return null;
}

function validateContent(english, indonesian) {
  if (!english) throw new Error('Missing ENGLISH section in LLM output');
  if (!indonesian) throw new Error('Missing INDONESIAN section in LLM output');
  if (english.length < 80) throw new Error(`English content too short: ${english.length} chars`);
  if (indonesian.length < 80) throw new Error(`Indonesian content too short: ${indonesian.length} chars`);
  if (english.startsWith('{') || indonesian.startsWith('{')) throw new Error('Content looks like JSON');
  log(`   Content validated: EN ${english.length} chars, ID ${indonesian.length} chars`);
}

// ──────────────────────────────────────────────────────────────
// FACEBOOK POSTING
// ──────────────────────────────────────────────────────────────

function postToPage(pageKey, message, imagePath = null) {
  if (!fs.existsSync(CONFIG.fbPagesConfig)) throw new Error('fb_pages.json not found');
  const pages = JSON.parse(fs.readFileSync(CONFIG.fbPagesConfig, 'utf8'));
  const page = pages[pageKey];
  if (!page) throw new Error(`Page config not found for: ${pageKey}`);

  log(`   Posting to ${pageKey}${imagePath ? ' (with image)' : ' (text-only)'}...`);

  const args = imagePath
    ? [CONFIG.fbScript, '--type', 'image', '--message', message, '--image-file', imagePath]
    : [CONFIG.fbScript, '--type', 'text', '--message', message];

  const result = spawnSync('node', args, {
    encoding: 'utf8',
    stdio: ['pipe', 'pipe', 'pipe'],
    env: {
      ...process.env,
      LONG_META_page_TOKEN: page.LONG_META_page_TOKEN,
      META_PAGE_ID: page.META_PAGE_ID,
      META_APP_SECRET: page.META_APP_SECRET,
    },
  });

  if (result.status !== 0) {
    throw new Error(`fb-post.js failed for ${pageKey}: ${result.stderr || result.stdout}`);
  }

  const stdout = result.stdout || '';
  const match = stdout.match(/Post ID: (\S+)/);
  const postId = match ? match[1] : `unknown_${Date.now()}`;
  log(`   ✅ ${pageKey} → Post ID: ${postId}`);

  return { success: true, postId, pageKey };
}

// ──────────────────────────────────────────────────────────────
// HISTORY
// ──────────────────────────────────────────────────────────────

function getArchivePath(basePath) {
  const now = new Date();
  const monthKey = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
  const dir = path.dirname(basePath);
  const ext = path.extname(basePath);
  const base = path.basename(basePath, ext);
  return path.join(dir, `${base}_${monthKey}${ext}`);
}

function rotateHistoryIfNeeded() {
  const archivePath = getArchivePath(CONFIG.postingHistory);
  
  // If current month archive doesn't exist and main file is large, rotate
  if (!fs.existsSync(archivePath) && fs.existsSync(CONFIG.postingHistory)) {
    const stats = fs.statSync(CONFIG.postingHistory);
    const sizeMB = stats.size / (1024 * 1024);
    
    if (sizeMB > 1) {  // Archive if > 1MB
      fs.copyFileSync(CONFIG.postingHistory, archivePath);
      // Keep only last 20 entries in main file
      let history = JSON.parse(fs.readFileSync(CONFIG.postingHistory, 'utf8'));
      if (history.length > 20) {
        history = history.slice(-20);
        fs.writeFileSync(CONFIG.postingHistory, JSON.stringify(history, null, 2));
        log(`   📦 History archived to ${path.basename(archivePath)}`);
      }
    }
  }
}

function saveHistory(marketData, postResults, topic, style) {
  // Rotate old history if needed
  rotateHistoryIfNeeded();
  
  let history = [];
  if (fs.existsSync(CONFIG.postingHistory)) {
    try { history = JSON.parse(fs.readFileSync(CONFIG.postingHistory, 'utf8')); } catch (e) {}
  }

  history.push({
    timestamp: new Date().toISOString(),
    topic,
    style: style.id,
    marketData: { btc: marketData.crypto.BTC, eth: marketData.crypto.ETH, nvda: marketData.stocks.NVDA },
    postResults,
    sources: marketData.sources,
  });

  // Keep only last 100 entries in current file
  if (history.length > 100) history = history.slice(-100);
  fs.mkdirSync(path.dirname(CONFIG.postingHistory), { recursive: true });
  fs.writeFileSync(CONFIG.postingHistory, JSON.stringify(history, null, 2));
}

function archiveContent(english, indonesian, topic) {
  if (!fs.existsSync(CONFIG.archiveDir)) fs.mkdirSync(CONFIG.archiveDir, { recursive: true });
  const ts = new Date().toISOString().replace(/[:.]/g, '-');
  fs.writeFileSync(path.join(CONFIG.archiveDir, `techtalk_${ts}.md`),
    `# ${topic}\n\n## English\n${english}\n\n## Indonesian\n${indonesian}\n`);
}

// ──────────────────────────────────────────────────────────────
// MAIN
// ──────────────────────────────────────────────────────────────

async function main() {
  log('═══════════════════════════════════════════════');
  log(`🚀 TechTalk Standalone Poster starting`);
  log(`   Mode: ${enOnly ? 'EN-only' : idOnly ? 'ID-only' : 'Both'} | Dry Run: ${dryRun}`);

  // 0. Validate configuration
  validateConfig();
  log('✅ Configuration validated');

  // 1. Safety lock
  checkSafetyLock();
  log('✅ Safety lock OK');

  // 2. State & topic selection
  const state = readState();
  const topic = pickTopic(state);
  const style = pickStyle(topic, state);
  log(`📌 Topic: ${topic} | Style: ${style.name}`);

  // 3. Market data
  log('📊 Fetching market data...');
  const marketData = await fetchMarketData();

  // 4. Research (context-aware, graceful fallback)
  log('🔬 Starting research layer...');
  let researchContext = { items: [], sources: [] };
  try {
    researchContext = await researchTopic(topic, style);
  } catch (err) {
    log(`   Research skipped (non-fatal): ${err.message}`);
  }

  // 4.5 Get previous angles for this topic
  const lastHooks = state.topicAngles?.[topic] || [];

  // 4.6 Pre-calculate visual context (preserves randomized features)
  const visualContext = {
    useAvatar: Math.random() > 0.5,
    perspective: PERSPECTIVES[Math.floor(Math.random() * PERSPECTIVES.length)]
  };

  // 5. Generate content (Consolidated call)
  log('🤖 Generating content & visual prompt via DeepSeek API...');
  let rawContent;
  try {
    rawContent = await generateContent(topic, style, marketData, researchContext, lastHooks, visualContext);
  } catch (err) {
    log(`❌ Generation failed: ${err.message}`);
    process.exit(1);
  }

  // 6. Parse & validate
  const english = extractSection(rawContent, 'ENGLISH');
  const indonesian = extractSection(rawContent, 'INDONESIAN');
  try {
    validateContent(english, indonesian);
  } catch (err) {
    log(`❌ Content validation failed: ${err.message}`);
    log(`   Raw LLM output (first 400 chars): ${rawContent.substring(0, 400)}`);
    process.exit(1);
  }

  // 7. Visual Generation (PHASE 5)
  let imagePath = null;
  try {
    imagePath = await processVisual(rawContent, topic);
  } catch (err) {
    log(`   Visual skipped (non-fatal): ${err.message}`);
  }

  // 8. Archive
  archiveContent(english, indonesian, topic);
  log('📁 Content archived');

  if (dryRun) {
    log('⚠️ DRY RUN — skipping Facebook posting');
    if (imagePath) log(`   Generated visual archived at: ${path.basename(imagePath)}`);
    log(`   Research sources: [${researchContext.sources.join(', ')}] (${researchContext.items.length} items)`);
    log(`   EN preview: ${english.substring(0, 150)}...`);
    log(`   ID preview: ${indonesian.substring(0, 150)}...`);
    process.exit(0);
  }

  // 7. Post to Facebook
  const postResults = {};

  if (!idOnly) {
    try {
      postResults.english = postToPage('techtalkintel', english, imagePath);
    } catch (err) {
      log(`❌ English page post failed: ${err.message}`);
      postResults.english = { success: false, reason: err.message };
    }
  } else {
    postResults.english = { success: false, reason: 'Skipped (ID-only mode)' };
    log('   ⏭ English page skipped (ID-only mode)');
  }

  if (!enOnly) {
    try {
      postResults.indonesian = postToPage('techtalkintelid', indonesian, imagePath);
    } catch (err) {
      log(`❌ Indonesian page post failed: ${err.message}`);
      postResults.indonesian = { success: false, reason: err.message };
    }
  } else {
    postResults.indonesian = { success: false, reason: 'Skipped (EN-only mode)' };
    log('   ⏭ Indonesian page skipped (EN-only mode)');
  }

  // 9. Save history & update state
  saveHistory(marketData, postResults, topic, style);
  
  // Update rotation history
  state.usedTopics = [...(state.usedTopics || []), topic].slice(-20);
  state.usedStyles = [...(state.usedStyles || []), style.id].slice(-20);
  
  // Update angle diversification (save the first sentence/hook of the EN post)
  const newHook = english.split(/[.!?]/)[0].trim();
  if (!state.topicAngles) state.topicAngles = {};
  if (!state.topicAngles[topic]) state.topicAngles[topic] = [];
  state.topicAngles[topic] = [newHook, ...(state.topicAngles[topic])].slice(0, 3);

  state.lastSuccessfulPost = new Date().toISOString();
  state.totalPosts = (state.totalPosts || 0) + 1;
  writeState(state);

  // 9. Summary & Telegram report
  const enOk = postResults.english?.success;
  const idOk = postResults.indonesian?.success;
  log('');
  log('═══════════ RESULT ═══════════');
  log(`Topic: ${topic}`);
  log(`EN page: ${enOk ? '✅ ' + postResults.english.postId : '⏭ ' + (postResults.english?.reason || 'failed')}`);
  log(`ID page: ${idOk ? '✅ ' + postResults.indonesian.postId : '⏭ ' + (postResults.indonesian?.reason || 'failed')}`);
  log('══════════════════════════════');

  // Build Telegram message
  const wibTime = new Date().toLocaleString('id-ID', { timeZone: 'Asia/Jakarta', hour: '2-digit', minute: '2-digit', hour12: false });
  const enLine = enOk
    ? `✅ <b>EN Page</b> — posted (<code>${postResults.english.postId}</code>)`
    : `⏭ <b>EN Page</b> — ${postResults.english?.reason || 'failed'}`;
  const idLine = idOk
    ? `✅ <b>ID Page</b> — posted (<code>${postResults.indonesian.postId}</code>)`
    : `⏭ <b>ID Page</b> — ${postResults.indonesian?.reason || 'failed'}`;

  const anyFailed = (!enOk && !idOnly) || (!idOk && !enOnly);
  const statusIcon = anyFailed ? '⚠️' : '🚀';

  const researchLine = researchContext.sources.length > 0
    ? `🔬 <b>Research:</b> ${researchContext.items.length} items from [${researchContext.sources.join(', ')}]`
    : `🔬 <b>Research:</b> LLM knowledge only (no external data)`;

  const tgMsg = [
    `${statusIcon} <b>TechTalk Auto-Post</b> — ${wibTime} WIB`,
    ``,
    `📌 <b>Topic:</b> ${topic}`,
    `🎨 <b>Style:</b> ${style.name}`,
    `📊 <b>Market:</b> BTC $${Math.round(marketData.crypto.BTC).toLocaleString()} | ETH $${Math.round(marketData.crypto.ETH).toLocaleString()} | NVDA $${marketData.stocks.NVDA}`,
    researchLine,
    ``,
    enLine,
    idLine,
  ].join('\n');

  if (!dryRun) await sendTelegram(tgMsg);

  if (!enOk && !idOk && !enOnly && !idOnly) {
    process.exit(1);
  }
}

main().catch(err => {
  log(`❌ FATAL ERROR: ${err.message}`);
  log(err.stack);
  process.exit(1);
});
