module.exports = {
  apps: [
    {
      name: 'techtalk-en-daily',
      script: './scripts/techtalk-post.js',
      args: '--en-only',
      interpreter: 'node',
      namespace: 'techtalk',
      cron_restart: '0 5,21 * * *',
      autorestart: false,
      env: {
        TZ: 'Asia/Jakarta',
        NODE_ENV: 'production'
      }
    },
    {
      name: 'techtalk-id-daily',
      script: './scripts/techtalk-post.js',
      args: '--id-only',
      interpreter: 'node',
      namespace: 'techtalk',
      cron_restart: '0 10,19 * * *',
      autorestart: false,
      env: {
        TZ: 'Asia/Jakarta',
        NODE_ENV: 'production'
      }
    },
    {
      name: 'techtalk-engagement',
      script: './scripts/techtalk-reply.js',
      interpreter: 'node',
      namespace: 'techtalk',
      cron_restart: '0 */4 * * *',
      autorestart: false,
      env: {
        TZ: 'Asia/Jakarta',
        NODE_ENV: 'production'
      }
    }
  ]
};
