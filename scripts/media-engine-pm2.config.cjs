const path = require("path");

/** Checkout root — works for ops clone and any worktree (no hardcoded absolute path). */
const ROOT = path.resolve(__dirname, "..");

function app(name, script, env = {}) {
  return {
    name,
    namespace: "media",
    script: `./scripts/${script}`,
    interpreter: "/bin/bash",
    cwd: ROOT,
    autorestart: true,
    watch: false,
    instances: 1,
    exec_mode: "fork",
    env: {
      TZ: "Asia/Jakarta",
      NODE_ENV: "production",
      ...env,
    },
    error_file: `./logs/${name}-error.log`,
    out_file: `./logs/${name}-out.log`,
    log_date_format: "YYYY-MM-DD HH:mm:ss",
  };
}

module.exports = {
  apps: [
    app("otonom-media-api", "run_media_engine_pm2.sh", {
      MEDIA_ENGINE_PORT: "8765",
    }),
    app("otonom-media-dashboard", "run_dashboard_pm2.sh", {
      MEDIA_ENGINE_PORT: "8765",
      DASHBOARD_PORT: "3100",
      DASHBOARD_MODE: "production",
    }),
    app("otonom-media-health", "run_health_monitor_pm2.sh", {
      MEDIA_ENGINE_PORT: "8765",
      DASHBOARD_PORT: "3100",
      PM2_HEALTH_INTERVAL_SECONDS: "60",
    }),
    app("otonom-media-publisher", "run_publish_worker_pm2.sh", {
      PUBLISH_WORKER_INTERVAL_SECONDS: "60",
      PUBLISH_WORKER_LIMIT: "5",
      // Empty = every media_profiles row (workspace-scoped Postiz vault).
      PUBLISH_WORKER_PROFILE: "",
    }),
    app("otonom-media-watch", "run_watch_poll_worker_pm2.sh", {
      // Sleep between worker loops (seconds). Channel poll_interval_minutes still gates.
      WATCH_POLL_INTERVAL_SECONDS: "86400",
      // Optional: limit to one workspace id, e.g. "techtalk"
      // WATCH_POLL_PROFILE: "",
    }),
  ],
};
