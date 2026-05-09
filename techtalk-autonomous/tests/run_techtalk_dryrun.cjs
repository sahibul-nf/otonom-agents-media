/**
 * TechTalk Standalone Test Runner
 * ================================
 * Tests the standalone techtalk-post.js script in dry-run mode
 * 
 * Usage:
 *   node run_techtalk_dryrun.cjs [--en-only|--id-only]
 */

const { spawn } = require('child_process');
const path = require('path');

const args = process.argv.slice(2);
const langArg = args.find(a => a === '--en-only' || a === '--id-only') || '';

console.log('🚀 Starting TechTalk Standalone Dry-Run Test');
console.log('═══════════════════════════════════════════════\n');

const scriptPath = path.join(__dirname, '../scripts/techtalk-post.js');
const childArgs = ['--dry-run'];
if (langArg) childArgs.push(langArg);

const child = spawn('node', [scriptPath, ...childArgs], {
    stdio: 'inherit',
    env: process.env,
});

child.on('close', (code) => {
    console.log('\n═══════════════════════════════════════════════');
    if (code === 0) {
        console.log('✅ Dry-run completed successfully');
    } else {
        console.log(`❌ Dry-run failed with code ${code}`);
    }
    process.exit(code);
});

child.on('error', (err) => {
    console.error('❌ Failed to start script:', err.message);
    process.exit(1);
});