#!/usr/bin/env node

/**
 * fb-post.js — Publish to a Facebook Page via Graph API
 * WITH SAFETY LOCK CHECK
 *
 * Usage:
 *   node fb-post.js --type text --message "Hello world"
 *   node fb-post.js --type image --message "Photo" --image-url "https://..."
 *   node fb-post.js --type image --message "Photo" --image-file ./pic.jpg
 *   node fb-post.js --type text --message "Post" --comment-link "https://example.com"
 *   node fb-post.js --type text --message "Post" --schedule "2025-12-25T10:00:00+0800"
 *
 * Env vars required:
 *   LONG_META_page_TOKEN  — Long-lived Page Access Token
 *   META_PAGE_ID          — Facebook Page ID
 *   META_APP_SECRET       — Meta App Secret (for appsecret_proof)
 */

import { createHmac } from "node:crypto";
import { readFile } from "node:fs/promises";
import { basename } from "node:path";
import { readFileSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

// --- Safety Lock Check ---
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const safetyLockPath = join(__dirname, '../config/fb_safety_lock.json');

if (existsSync(safetyLockPath)) {
  const safetyLock = JSON.parse(readFileSync(safetyLockPath, 'utf8'));
  if (safetyLock.enabled === false) {
    console.error("❌ SAFETY LOCK ENGAGED - Facebook posting disabled");
    console.error(`   Reason: ${safetyLock.reason}`);
    console.error("   Requirements:");
    safetyLock.requirements.forEach(req => console.error(`   • ${req}`));
    process.exit(1);
  }
}

// --- Config ---

const PAGE_TOKEN = process.env.LONG_META_page_TOKEN;
const PAGE_ID = process.env.META_PAGE_ID;
const APP_SECRET = process.env.META_APP_SECRET;
const API_VERSION = "v25.0";
const BASE = `https://graph.facebook.com/${API_VERSION}`;

if (!PAGE_TOKEN || !PAGE_ID || !APP_SECRET) {
  console.error(
    "Error: missing env vars. Required:\n" +
      "  LONG_META_page_TOKEN\n" +
      "  META_PAGE_ID\n" +
      "  META_APP_SECRET"
  );
  process.exit(1);
}

// --- Helpers ---

function proof() {
  return createHmac("sha256", APP_SECRET).update(PAGE_TOKEN).digest("hex");
}

function parseArgs(argv) {
  const args = {};
  for (let i = 2; i < argv.length; i++) {
    if (argv[i].startsWith("--")) {
      const key = argv[i].slice(2);
      const val = argv[i + 1];
      if (val && !val.startsWith("--")) {
        args[key] = val;
        i++;
      } else {
        args[key] = true;
      }
    }
  }
  return args;
}

async function api(endpoint, body, formData = false) {
  const url = `${BASE}${endpoint}`;
  const opts = { method: "POST" };

  if (formData) {
    body.append("access_token", PAGE_TOKEN);
    body.append("appsecret_proof", proof());
    opts.body = body;
  } else {
    const p = new URLSearchParams(body);
    p.append("access_token", PAGE_TOKEN);
    p.append("appsecret_proof", proof());
    opts.body = p.toString();
    opts.headers = { "Content-Type": "application/x-www-form-urlencoded" };
  }

  const res = await fetch(url, opts);
  const data = await res.json();

  if (!res.ok) {
    throw new Error(
      `Graph API ${res.status}: ${data?.error?.message || JSON.stringify(data)}`
    );
  }
  return data;
}

// --- Post functions ---

async function postText(msg, schedule) {
  const body = { message: msg };
  if (schedule) {
    body.published = "false";
    body.scheduled_publish_time = String(
      Math.floor(new Date(schedule).getTime() / 1000)
    );
  }

  const data = await api(`/${PAGE_ID}/feed`, body);
  console.log(`Post ID: ${data.id}`);
  return data;
}

async function postImage(msg, imageUrl, imageFile, schedule) {
  const body = new FormData();
  body.append("message", msg);

  if (imageUrl) {
    body.append("url", imageUrl);
  } else if (imageFile) {
    const buf = await readFile(imageFile);
    const blob = new Blob([buf]);
    body.append("source", blob, basename(imageFile));
  }

  if (schedule) {
    body.append("published", "false");
    body.append(
      "scheduled_publish_time",
      String(Math.floor(new Date(schedule).getTime() / 1000))
    );
  }

  const data = await api(`/${PAGE_ID}/photos`, body, true);
  console.log(`Post ID: ${data.post_id || data.id}`);
  return data;
}

// --- Main ---

async function main() {
  const args = parseArgs(process.argv);

  if (!args.type || !args.message) {
    console.error(
      "Usage: node fb-post.js --type text|image --message '...' [--image-url URL] [--image-file PATH] [--comment-link URL] [--schedule ISO_DATE]"
    );
    process.exit(1);
  }

  try {
    let result;
    if (args.type === "text") {
      result = await postText(args.message, args.schedule);
      if (args["comment-link"]) {
        // Post the link as a comment
        const commentBody = { message: args["comment-link"] };
        await api(`/${result.id}/comments`, commentBody);
        console.log(`Comment with link posted to ${result.id}`);
      }
    } else if (args.type === "image") {
      result = await postImage(
        args.message,
        args["image-url"],
        args["image-file"],
        args.schedule
      );
    } else {
      console.error(`Unknown type: ${args.type}. Use 'text' or 'image'.`);
      process.exit(1);
    }

    console.log("✅ Published successfully");
    return result;
  } catch (err) {
    console.error("❌ Failed:", err.message);
    process.exit(1);
  }
}

main();