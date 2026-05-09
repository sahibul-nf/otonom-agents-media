#!/usr/bin/env node
/**
 * TechTalk Performance Auditor
 * =============================
 * Analyzes posting history and (optionally) fetches engagement data
 * from Facebook Graph API to determine top-performing topics.
 *
 * Usage:
 *   node techtalk-audit.js              # Local analysis only
 *   node techtalk-audit.js --fetch      # Fetch engagement from FB API
 *   node techtalk-audit.js --weekly     # Generate weekly report
 */

'use strict';

const fs = require('fs');
const path = require('path');

// Load environment variables
try {
  const envPath = path.join(__dirname, '../.env');
  if (fs.existsSync(envPath)) {
    require('dotenv').config({ path: envPath });
  }
} catch (e) {}

const CONFIG = {
  postingHistory: path.join(__dirname, '../config/posting_history.json'),
  stateFile: path.join(__dirname, '../config/techtalk_state.json'),
  auditReport: path.join(__dirname, '../config/performance_audit.json'),
  fbPagesConfig: path.join(__dirname, '../config/fb_pages.json'),
  logFile: path.join(__dirname, '../logs/techtalk-audit.log'),
};

function log(msg) {
  const ts = new Date().toISOString();
  const line = `[${ts}] ${msg}`;
  console.log(line);
  try {
    fs.appendFileSync(CONFIG.logFile, line + '\n');
  } catch (e) {}
}

// ──────────────────────────────────────────────────────────────
// DATA LOADING
// ──────────────────────────────────────────────────────────────

function loadPostingHistory() {
  try {
    return JSON.parse(fs.readFileSync(CONFIG.postingHistory, 'utf8'));
  } catch (e) {
    log(`❌ Failed to load posting history: ${e.message}`);
    return [];
  }
}

function loadState() {
  try {
    return JSON.parse(fs.readFileSync(CONFIG.stateFile, 'utf8'));
  } catch (e) {
    return { topicPerformance: {} };
  }
}

function saveState(state) {
  fs.writeFileSync(CONFIG.stateFile, JSON.stringify(state, null, 2));
}

// ──────────────────────────────────────────────────────────────
// LOCAL ANALYSIS (without FB API)
// ──────────────────────────────────────────────────────────────

function analyzeTopicPerformance(history) {
  const topicStats = {};
  const styleStats = {};
  
  for (const entry of history) {
    const topic = entry.topic;
    const style = entry.style;
    const enSuccess = entry.postResults?.english?.success;
    const idSuccess = entry.postResults?.indonesian?.success;
    
    // Topic analysis
    if (!topicStats[topic]) {
      topicStats[topic] = { posts: 0, successful: 0, failed: 0 };
    }
    topicStats[topic].posts++;
    if (enSuccess || idSuccess) {
      topicStats[topic].successful++;
    } else {
      topicStats[topic].failed++;
    }
    
    // Style analysis
    if (style) {
      if (!styleStats[style]) {
        styleStats[style] = { posts: 0, successful: 0 };
      }
      styleStats[style].posts++;
      if (enSuccess || idSuccess) {
        styleStats[style].successful++;
      }
    }
  }
  
  // Calculate success rates
  for (const topic in topicStats) {
    const s = topicStats[topic];
    s.successRate = ((s.successful / s.posts) * 100).toFixed(1);
  }
  
  for (const style in styleStats) {
    const s = styleStats[style];
    s.successRate = ((s.successful / s.posts) * 100).toFixed(1);
  }
  
  return { topicStats, styleStats };
}

function calculateTopicWeights(topicStats, totalPosts) {
  const weights = {};
  
  // Base weight calculation
  for (const [topic, stats] of Object.entries(topicStats)) {
    // Factors:
    // 1. Success rate (higher = better)
    // 2. Recency penalty (topics posted recently get lower weight)
    // 3. Volume factor (topics with more data are more reliable)
    
    const successWeight = parseFloat(stats.successRate) / 100;
    const volumeFactor = Math.min(stats.posts / 5, 1); // Max at 5+ posts
    
    weights[topic] = {
      baseWeight: (successWeight * 0.7 + volumeFactor * 0.3),
      stats,
    };
  }
  
  // Normalize weights to sum to 1
  const totalWeight = Object.values(weights).reduce((sum, w) => sum + w.baseWeight, 0);
  for (const topic in weights) {
    weights[topic].normalizedWeight = weights[topic].baseWeight / totalWeight;
  }
  
  return weights;
}

// ──────────────────────────────────────────────────────────────
// FACEBOOK ENGAGEMENT FETCH (optional)
// ──────────────────────────────────────────────────────────────

async function fetchPostEngagement(postId, accessToken) {
  try {
    const fields = 'likes.summary(true),comments.summary(true),shares';
    const url = `https://graph.facebook.com/v18.0/${postId}?fields=${fields}&access_token=${accessToken}`;
    
    const res = await fetch(url, { signal: AbortSignal.timeout(10000) });
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }
    
    const data = await res.json();
    return {
      likes: data.likes?.summary?.total_count || 0,
      comments: data.comments?.summary?.total_count || 0,
      shares: data.shares?.count || 0,
    };
  } catch (e) {
    return null;
  }
}

async function enrichWithEngagement(history, pages) {
  log('Fetching engagement data from Facebook...');
  
  const enriched = [];
  let fetchCount = 0;
  
  for (const entry of history.slice(-20)) {  // Last 20 posts only
    const enrichedEntry = { ...entry };
    
    for (const [lang, result] of Object.entries(entry.postResults || {})) {
      if (result.success && result.postId) {
        const pageKey = lang === 'english' ? 'techtalkintel' : 'techtalkintelid';
        const page = pages[pageKey];
        
        if (page?.LONG_META_page_TOKEN) {
          const engagement = await fetchPostEngagement(result.postId, page.LONG_META_page_TOKEN);
          if (engagement) {
            enrichedEntry.postResults[lang].engagement = engagement;
            fetchCount++;
            
            // Rate limiting
            await new Promise(r => setTimeout(r, 500));
          }
        }
      }
    }
    
    enriched.push(enrichedEntry);
  }
  
  log(`Fetched engagement for ${fetchCount} posts`);
  return enriched;
}

// ──────────────────────────────────────────────────────────────
// REPORTING
// ──────────────────────────────────────────────────────────────

function generateReport(analysis, weights) {
  const lines = [];
  
  lines.push('╔════════════════════════════════════════════════════════╗');
  lines.push('║        TECHTALK PERFORMANCE AUDIT REPORT               ║');
  lines.push('╚════════════════════════════════════════════════════════╝');
  lines.push('');
  
  // Topic performance
  lines.push('📊 TOPIC PERFORMANCE (sorted by success rate)');
  lines.push('─'.repeat(60));
  
  const sortedTopics = Object.entries(analysis.topicStats)
    .sort((a, b) => parseFloat(b[1].successRate) - parseFloat(a[1].successRate));
  
  for (const [topic, stats] of sortedTopics) {
    const weight = weights[topic]?.normalizedWeight 
      ? `(${Math.round(weights[topic].normalizedWeight * 100)}%)`
      : '';
    lines.push(`${topic.padEnd(30)} ${stats.successful}/${stats.posts} ✅ ${stats.successRate}% ${weight}`);
  }
  
  lines.push('');
  
  // Style performance
  lines.push('🎨 STYLE PERFORMANCE');
  lines.push('─'.repeat(60));
  
  const sortedStyles = Object.entries(analysis.styleStats)
    .sort((a, b) => parseFloat(b[1].successRate) - parseFloat(a[1].successRate));
  
  for (const [style, stats] of sortedStyles) {
    lines.push(`${style.padEnd(20)} ${stats.successful}/${stats.posts} ✅ ${stats.successRate}%`);
  }
  
  lines.push('');
  
  // Recommendations
  lines.push('💡 RECOMMENDATIONS');
  lines.push('─'.repeat(60));
  
  const topTopics = sortedTopics.slice(0, 5);
  const bottomTopics = sortedTopics.slice(-3);
  
  lines.push('Top performing topics (increase frequency):');
  topTopics.forEach(([t], i) => lines.push(`  ${i + 1}. ${t}`));
  
  lines.push('');
  lines.push('Underperforming topics (reduce frequency or improve content):');
  bottomTopics.forEach(([t], i) => lines.push(`  ${i + 1}. ${t}`));
  
  return lines.join('\n');
}

// ──────────────────────────────────────────────────────────────
// MAIN
// ──────────────────────────────────────────────────────────────

async function main() {
  const args = process.argv.slice(2);
  const fetchEngagement = args.includes('--fetch');
  const weeklyReport = args.includes('--weekly');
  
  log('═══════════════════════════════════════════════');
  log('📈 TechTalk Performance Auditor starting');
  
  // Load data
  let history = loadPostingHistory();
  if (history.length === 0) {
    log('No posting history found');
    process.exit(1);
  }
  
  log(`Loaded ${history.length} posting history entries`);
  
  // Optional: fetch engagement data
  if (fetchEngagement) {
    if (!fs.existsSync(CONFIG.fbPagesConfig)) {
      log('❌ Facebook pages config not found');
    } else {
      const pages = JSON.parse(fs.readFileSync(CONFIG.fbPagesConfig, 'utf8'));
      history = await enrichWithEngagement(history, pages);
    }
  }
  
  // Analyze
  const analysis = analyzeTopicPerformance(history);
  const weights = calculateTopicWeights(analysis.topicStats, history.length);
  
  // Update state with weights
  const state = loadState();
  state.topicWeights = weights;
  state.lastAudit = new Date().toISOString();
  saveState(state);
  
  log('Updated topic weights in state file');
  
  // Generate report
  const report = generateReport(analysis, weights);
  console.log('\n' + report);
  
  // Save report
  fs.writeFileSync(CONFIG.auditReport, JSON.stringify({
    timestamp: new Date().toISOString(),
    analysis,
    weights,
    report,
  }, null, 2));
  
  log(`Report saved to ${CONFIG.auditReport}`);
  
  // Telegram notification for weekly report
  if (weeklyReport && process.env.TELEGRAM_BOT_TOKEN) {
    const topTopic = Object.entries(analysis.topicStats)
      .sort((a, b) => parseFloat(b[1].successRate) - parseFloat(a[1].successRate))[0];
    
    const message = `📊 <b>Weekly TechTalk Audit</b>\n\n` +
      `📈 Top Topic: <b>${topTopic[0]}</b> (${topTopic[1].successRate}% success)\n` +
      `📉 Total Posts: ${history.length}\n` +
      `🎯 Topics Analyzed: ${Object.keys(analysis.topicStats).length}`;
    
    try {
      const payload = {
        chat_id: process.env.TELEGRAM_CHAT_ID,
        text: message,
        parse_mode: 'HTML',
      };
      if (process.env.TELEGRAM_THREAD_ID) {
        payload.message_thread_id = process.env.TELEGRAM_THREAD_ID;
      }
      await fetch(`https://api.telegram.org/bot${process.env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      log('Weekly report sent to Telegram');
    } catch (e) {
      log(`Failed to send Telegram: ${e.message}`);
    }
  }
}

main().catch(err => {
  log(`❌ FATAL ERROR: ${err.message}`);
  log(err.stack);
  process.exit(1);
});
