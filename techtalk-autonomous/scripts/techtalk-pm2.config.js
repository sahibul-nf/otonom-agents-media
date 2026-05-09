/**
 * TechTalk Autonomous Posting — PM2 Ecosystem Config
 *
 * Schedule (Asia/Jakarta / WIB):
 *   English page : 05:00, 21:00
 *   Indonesian pg : 10:00, 19:00
 *
 * To deploy:
 *   pm2 start techtalk-pm2.config.js
 *   pm2 save
 *
 * To stop:
 *   pm2 delete techtalk-en-daily techtalk-id-daily
 */

module.exports = {
  apps: [
    {
      name: 'techtalk-en-daily',
      script: './scripts/techtalk-post.js',
      args: '--en-only',
      cron_restart: '0 5,21 * * *',  // 05:00, 21:00 WIB
      autorestart: false,                // don't loop — run once per trigger
      watch: false,
      instances: 1,
      exec_mode: 'fork',
      env: {
        TZ: 'Asia/Jakarta',
        NODE_ENV: 'production',
        NODE_PATH: './node_modules',
      },
      error_file: './logs/techtalk-en-error.log',
      out_file: './logs/techtalk-en-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
    },
    {
      name: 'techtalk-id-daily',
      script: './scripts/techtalk-post.js',
      args: '--id-only',
      cron_restart: '0 10,19 * * *',  // 10:00, 19:00 WIB
      autorestart: false,
      watch: false,
      instances: 1,
      exec_mode: 'fork',
      env: {
        TZ: 'Asia/Jakarta',
        NODE_ENV: 'production',
        NODE_PATH: './node_modules',
      },
      error_file: './logs/techtalk-id-error.log',
      out_file: './logs/techtalk-id-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
    },
    {
      name: 'techtalk-engagement',
      script: './scripts/techtalk-reply.js',
      cron_restart: '0 */4 * * *',  // Every 4 hours
      autorestart: false,
      watch: false,
      instances: 1,
      exec_mode: 'fork',
      env: {
        TZ: 'Asia/Jakarta',
        NODE_ENV: 'production',
        NODE_PATH: './node_modules',
      },
      error_file: './logs/techtalk-reply-error.log',
      out_file: './logs/techtalk-reply-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
    },
  ],
};
