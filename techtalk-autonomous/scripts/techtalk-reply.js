#!/usr/bin/env node
/**
 * TechTalk Engagement Engine — Auto-Reply to Comments
 * ====================================================
 * Runs via PM2 cron every 4-6 hours to check and reply to comments
 * on recent Facebook posts.
 *
 * Usage:
 *   node techtalk-reply.js --dry-run    # Check only, don't reply
 *   node techtalk-reply.js              # Normal operation
 */

'use strict';

const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');
const crypto = require('crypto');

// Load environment variables
try {
  const envPath = path.join(__dirname, '../.env');
  if (fs.existsSync(envPath)) {
    require('dotenv').config({ path: envPath });
  }
} catch (e) {
  // dotenv not installed
}

// ──────────────────────────────────────────────────────────────
// CONFIGURATION
// ──────────────────────────────────────────────────────────────

const CONFIG = {
  deepseekApiKey: process.env.DEEPSEEK_API_KEY || '',
  deepseekBaseUrl: process.env.DEEPSEEK_BASE_URL || 'https://api.deepseek.com/v1',
  deepseekModel: process.env.DEEPSEEK_MODEL || 'deepseek-chat',
  fbPagesConfig: path.join(__dirname, '../config/fb_pages.json'),
  postingHistory: path.join(__dirname, '../config/posting_history.json'),
  replyHistory: path.join(__dirname, '../config/reply_history.json'),
  logFile: path.join(__dirname, '../logs/techtalk-reply.log'),
  apiVersion: 'v25.0',           // Updated to latest version
  // Reply settings
  maxRepliesPerRun: 5,           // Max replies per execution
  replyCooldownHours: 24,        // Don't reply to same user within X hours
  checkLastNPosts: 3,            // Check comments on last N posts
  minCommentLength: 10,          // Skip very short comments
  maxCommentLength: 500,         // Skip very long comments (likely spam)
};

// Toxic/spam keywords to filter
const BLOCKED_KEYWORDS = [
  'http', 'https', 'www.', '.com', '.net', '.org',  // Links
  'click here', 'buy now', 'limited time', 'act now', // Spam
  'free money', 'make money', 'earn $', 'cash app',   // Scams
  'follow me', 'check my profile', 'dm me',           // Self-promo
];

// ──────────────────────────────────────────────────────────────
// LOGGING
// ──────────────────────────────────────────────────────────────

function log(msg) {
  const ts = new Date().toISOString();
  const line = `[${ts}] ${msg}`;
  console.log(line);
  try {
    fs.appendFileSync(CONFIG.logFile, line + '\n');
  } catch (e) {}
}

// ──────────────────────────────────────────────────────────────
// REPLY HISTORY MANAGEMENT
// ──────────────────────────────────────────────────────────────

function loadReplyHistory() {
  if (!fs.existsSync(CONFIG.replyHistory)) {
    return { replies: [], lastRun: null };
  }
  try {
    return JSON.parse(fs.readFileSync(CONFIG.replyHistory, 'utf8'));
  } catch (e) {
    return { replies: [], lastRun: null };
  }
}

function saveReplyHistory(history) {
  fs.mkdirSync(path.dirname(CONFIG.replyHistory), { recursive: true });
  fs.writeFileSync(CONFIG.replyHistory, JSON.stringify(history, null, 2));
}

function hasRecentlyReplied(userId, commentId, history) {
  const cutoff = Date.now() - (CONFIG.replyCooldownHours * 60 * 60 * 1000);
  return history.replies.some(r => 
    (r.userId === userId || r.commentId === commentId) && 
    new Date(r.timestamp).getTime() > cutoff
  );
}

// ──────────────────────────────────────────────────────────────
// COMMENT FILTERING
// ──────────────────────────────────────────────────────────────

function shouldReply(comment) {
  const text = comment.message?.toLowerCase() || '';
  
  // Length check
  if (text.length < CONFIG.minCommentLength) {
    return { shouldReply: false, reason: 'Too short' };
  }
  if (text.length > CONFIG.maxCommentLength) {
    return { shouldReply: false, reason: 'Too long (spam?)' };
  }
  
  // Blocked keywords
  for (const keyword of BLOCKED_KEYWORDS) {
    if (text.includes(keyword.toLowerCase())) {
      return { shouldReply: false, reason: `Contains blocked keyword: ${keyword}` };
    }
  }
  
  // Skip if already replied
  const history = loadReplyHistory();
  if (hasRecentlyReplied(comment.from.id, comment.id, history)) {
    return { shouldReply: false, reason: 'Already replied recently' };
  }
  
  // Prioritize questions
  const isQuestion = text.includes('?') || 
    /\b(what|how|why|when|where|who|which|can|could|would|will|is|are|do|does)\b/.test(text);
  
  return { shouldReply: true, priority: isQuestion ? 2 : 1 };
}

// ──────────────────────────────────────────────────────────────
// FACEBOOK GRAPH API HELPERS
// ──────────────────────────────────────────────────────────────

function getAppSecretProof(accessToken, appSecret) {
  return crypto.createHmac('sha256', appSecret).update(accessToken).digest('hex');
}

// ──────────────────────────────────────────────────────────────
// FACEBOOK GRAPH API
// ──────────────────────────────────────────────────────────────

async function fetchComments(pageId, postId, accessToken, appSecret) {
  try {
    const proof = getAppSecretProof(accessToken, appSecret);
    const url = `https://graph.facebook.com/${CONFIG.apiVersion}/${postId}/comments?access_token=${accessToken}&appsecret_proof=${proof}&limit=20&fields=id,message,from,created_time`;
    const res = await fetch(url, { signal: AbortSignal.timeout(15000) });
    
    if (!res.ok) {
      const err = await res.text();
      throw new Error(`Graph API error: ${res.status} - ${err}`);
    }
    
    const data = await res.json();
    return data.data || [];
  } catch (e) {
    log(`   ❌ Failed to fetch comments: ${e.message}`);
    return [];
  }
}

async function postReply(commentId, message, accessToken, appSecret) {
  try {
    const proof = getAppSecretProof(accessToken, appSecret);
    const url = `https://graph.facebook.com/${CONFIG.apiVersion}/${commentId}/comments`;
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        access_token: accessToken,
        appsecret_proof: proof,
      }),
      signal: AbortSignal.timeout(15000),
    });
    
    if (!res.ok) {
      const err = await res.text();
      throw new Error(`Reply failed: ${res.status} - ${err}`);
    }
    
    const data = await res.json();
    return { success: true, replyId: data.id };
  } catch (e) {
    return { success: false, error: e.message };
  }
}

// ──────────────────────────────────────────────────────────────
// CONTENT GENERATION
// ──────────────────────────────────────────────────────────────

function buildReplyPrompt(commentText, postTopic, isQuestion) {
  const persona = `You are TechTalk Intel, a knowledgeable tech analyst. You're replying to a comment on your Facebook post about "${postTopic}".`;
  
  const tone = isQuestion 
    ? 'Be helpful and informative. Provide specific insights where possible.'
    : 'Be conversational and engaging. Acknowledge their perspective.';
  
  const rules = `
Rules:
1. Keep reply under 150 characters (concise for social media)
2. Be professional but friendly
3. Don't use hashtags in replies
4. Don't be overly promotional
5. If it's a question you can't answer well, give a thoughtful acknowledgment
6. Use max 1 emoji if appropriate
7. NEVER include the comment text in your reply
`;

  return `${persona}

Original comment: "${commentText}"

${tone}
${rules}

Write a brief, engaging reply:`;
}

async function generateReply(commentText, postTopic, isQuestion) {
  log(`   🤖 Generating reply via DeepSeek...`);
  
  const prompt = buildReplyPrompt(commentText, postTopic, isQuestion);
  
  try {
    const res = await fetch(`${CONFIG.deepseekBaseUrl}/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${CONFIG.deepseekApiKey}`,
      },
      body: JSON.stringify({
        model: CONFIG.deepseekModel,
        messages: [{ role: 'user', content: prompt }],
        max_tokens: 100,
        temperature: 0.7,
      }),
    });
    
    if (!res.ok) {
      const err = await res.text();
      throw new Error(`DeepSeek API error: ${res.status}`);
    }
    
    const json = await res.json();
    const reply = json.choices?.[0]?.message?.content?.trim();
    
    if (!reply) {
      throw new Error('Empty response from DeepSeek');
    }
    
    // Clean up reply
    return reply
      .replace(/^["']|["']$/g, '')  // Remove surrounding quotes
      .replace(/\n/g, ' ')           // Single line
      .substring(0, 200);             // Hard limit
      
  } catch (e) {
    log(`   ⚠️ Generation failed: ${e.message}`);
    // Fallback replies
    const fallbacks = [
      "Thanks for sharing your thoughts! 🙏",
      "Great point! Appreciate the insight.",
      "Interesting perspective! Thanks for engaging.",
      "Couldn't agree more! 👍",
    ];
    return fallbacks[Math.floor(Math.random() * fallbacks.length)];
  }
}

// ──────────────────────────────────────────────────────────────
// MAIN LOGIC
// ──────────────────────────────────────────────────────────────

async function processPage(pageKey, pageConfig, dryRun = false) {
  log(`\n📄 Processing page: ${pageKey}`);
  
  // Get recent posts from history
  let history = [];
  try {
    history = JSON.parse(fs.readFileSync(CONFIG.postingHistory, 'utf8'));
  } catch (e) {
    log(`   ⚠️ Could not load posting history`);
    return { checked: 0, replied: 0 };
  }
  
  // Filter posts for this page
  const pagePosts = history
    .filter(h => h.postResults?.[pageKey === 'techtalkintel' ? 'english' : 'indonesian']?.success)
    .slice(-CONFIG.checkLastNPosts);
  
  if (pagePosts.length === 0) {
    log(`   No recent posts found for this page`);
    return { checked: 0, replied: 0 };
  }
  
  log(`   Found ${pagePosts.length} recent posts to check`);
  
  let totalChecked = 0;
  let totalReplied = 0;
  const replyHistory = loadReplyHistory();
  
  for (const post of pagePosts) {
    const postResult = post.postResults[pageKey === 'techtalkintel' ? 'english' : 'indonesian'];
    const postId = postResult.postId;
    const topic = post.topic || 'Technology';
    
    if (!postId) continue;
    
    log(`   Checking post: ${postId.substring(0, 30)}...`);
    
    // Fetch comments
    const comments = await fetchComments(pageConfig.META_PAGE_ID, postId, pageConfig.LONG_META_page_TOKEN, pageConfig.META_APP_SECRET);
    totalChecked += comments.length;
    
    if (comments.length === 0) {
      log(`   No comments on this post`);
      continue;
    }
    
    // Filter and prioritize comments
    const candidates = comments
      .map(c => ({ ...c, filterResult: shouldReply(c) }))
      .filter(c => c.filterResult.shouldReply)
      .sort((a, b) => b.filterResult.priority - a.filterResult.priority);
    
    log(`   ${candidates.length}/${comments.length} comments eligible for reply`);
    
    // Reply to top candidates
    for (const comment of candidates.slice(0, 2)) {  // Max 2 per post
      if (totalReplied >= CONFIG.maxRepliesPerRun) {
        log(`   Reached max replies per run (${CONFIG.maxRepliesPerRun})`);
        break;
      }
      
      const isQuestion = comment.filterResult.priority === 2;
      log(`   💬 Replying to: "${comment.message.substring(0, 50)}..."`);
      
      // Generate reply
      const replyText = await generateReply(comment.message, topic, isQuestion);
      log(`   📝 Generated: "${replyText}"`);
      
      if (dryRun) {
        log(`   ⏭ DRY RUN - would reply with above text`);
        continue;
      }
      
      // Post reply
      const result = await postReply(comment.id, replyText, pageConfig.LONG_META_page_TOKEN, pageConfig.META_APP_SECRET);
      
      if (result.success) {
        log(`   ✅ Reply posted: ${result.replyId}`);
        totalReplied++;
        
        // Record in history
        replyHistory.replies.push({
          timestamp: new Date().toISOString(),
          postId,
          commentId: comment.id,
          userId: comment.from.id,
          userName: comment.from.name,
          originalComment: comment.message.substring(0, 100),
          replyText,
          replyId: result.replyId,
          pageKey,
        });
      } else {
        log(`   ❌ Reply failed: ${result.error}`);
      }
    }
  }
  
  // Save history
  if (!dryRun && totalReplied > 0) {
    replyHistory.lastRun = new Date().toISOString();
    saveReplyHistory(replyHistory);
  }
  
  return { checked: totalChecked, replied: totalReplied };
}

// ──────────────────────────────────────────────────────────────
// MAIN
// ──────────────────────────────────────────────────────────────

async function main() {
  const args = process.argv.slice(2);
  const dryRun = args.includes('--dry-run');
  
  log('═══════════════════════════════════════════════');
  log(`🤖 TechTalk Engagement Engine starting`);
  log(`   Mode: ${dryRun ? 'DRY RUN' : 'LIVE'}`);
  
  // Validate config
  if (!CONFIG.deepseekApiKey) {
    log('❌ DEEPSEEK_API_KEY not set');
    process.exit(1);
  }
  
  // Load page configs
  if (!fs.existsSync(CONFIG.fbPagesConfig)) {
    log('❌ Facebook pages config not found');
    process.exit(1);
  }
  
  const pages = JSON.parse(fs.readFileSync(CONFIG.fbPagesConfig, 'utf8'));
  
  let totalStats = { checked: 0, replied: 0 };
  
  // Process each page
  for (const [pageKey, pageConfig] of Object.entries(pages)) {
    if (!pageConfig.LONG_META_page_TOKEN) continue;
    
    const stats = await processPage(pageKey, pageConfig, dryRun);
    totalStats.checked += stats.checked;
    totalStats.replied += stats.replied;
  }
  
  log('\n═══════════ SUMMARY ═══════════');
  log(`Total comments checked: ${totalStats.checked}`);
  log(`Total replies ${dryRun ? 'would be' : ''} posted: ${totalStats.replied}`);
  log('═══════════════════════════════');
}

main().catch(err => {
  log(`❌ FATAL ERROR: ${err.message}`);
  log(err.stack);
  process.exit(1);
});
