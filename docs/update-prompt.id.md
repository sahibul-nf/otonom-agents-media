<!-- solo-dev-ai-kit:managed -->
# Update workflow kit — tempel ke AI agent

Pakai saat **solo-dev-ai-kit** ada rilis baru dan **project app** kamu sudah punya workflow ter-install.

Setelah bootstrap, salinan ada di project sebagai **`docs/update-prompt.id.md`** — agent bisa ikuti saat kamu bilang *perbarui workflow kit* atau `/update` tanpa paste file ini.

Buka **project app** di Cursor Agent mode. Tempel di bawah. **Agent yang jalankan terminal** — bukan kamu.

---

Update **solo-dev-ai-kit** di project ini ke versi kit terbaru. Saya tidak menjalankan terminal sendiri — kamu yang jalankan.

## Sumber kit (harus terbaru)

```bash
# Kalau kit clone lokal — pull dulu:
cd [path/to/solo-dev-ai-kit] && git pull

# Atau clone baru:
git clone https://github.com/sahibul-nf/solo-dev-ai-kit.git /tmp/solo-dev-ai-kit
```

## Sebelum mengubah apa pun

1. Baca `.workflow-kit/installed` — catat `kit_version`, `tools`, `app_stack`.
2. Baca `.workflow-kit.env` — terutama `GH_PROJECT_NUM`, branch, `CI_TEST_COMMAND`, `VERIFY_MAX_ROUNDS`, `APP_STACK`.
3. Beri tahu saya loncatan versi (mis. `6` → `7`) dan apa yang akan di-update.
4. **Dry-run dulu** (disarankan):

```bash
/path/to/solo-dev-ai-kit/bootstrap.sh --target . --dry-run
```

Tinjau baris `[dry-run]`. Tidak ada file yang diubah.

## Re-bootstrap (update aman)

Jalankan dari **root project app**:

```bash
/path/to/solo-dev-ai-kit/bootstrap.sh --target .
```

**Tidak perlu mengulang semua flag.** Jika `.workflow-kit.env` sudah ada, bootstrap **merge** otomatis:

| Dipertahankan otomatis | Hanya berubah jika kamu kirim flag CLI |
|------------------------|----------------------------------------|
| `GH_PROJECT_NUM`, `GH_PROJECT_OWNER` | `--repo` |
| `GH_REPO`, branch, `SINGLE_BRANCH` | `--integration-branch`, `--production-branch`, `--main-only` |
| `WORKFLOW_TOOLS`, `CI_TEST_COMMAND` | `--tools`, `--ci-test` |
| `APP_STACK`, `VERIFY_MAX_ROUNDS` | `--app-stack`, `--verify-max-rounds` |
| `EXTRA_LABELS`, `HAS_CLIENT_REPORTS` | `--extra-labels`, `--client-reports` |

Sebelum menulis, bootstrap menyimpan `.workflow-kit/env.backup`.

### Tanpa `--force` (disarankan)

**Ter-update:** skrip, cursor rules/commands, sebagian besar `docs/*`, issue templates, `.workflow-kit/installed`.

**`AGENTS.md`:** auto-merge bagian workflow kit (intent router, phases, self-verify, Related, dll.) dan **pertahankan** section project-specific (mis. PukatFlow) atau isi di `<!-- workflow-kit:project-specific -->`.

**Tetap (jika sudah ada):** `docs/how-to-run.md`.

Setelah update: cek `git diff AGENTS.md` — blok project-specific harus masih ada.

### Dengan `--force` (hanya jika saya minta)

Menimpa `AGENTS.md` (termasuk section project-specific) dan `docs/how-to-run.md`. Ingatkan saya sebelum pakai `--force`.

## Setelah bootstrap

1. Jalankan `./scripts/gh-check-ui-tools.sh`.
2. Tampilkan `git diff --stat` file workflow.
3. Bandingkan `kit_version` baru di `.workflow-kit/installed`.
4. Konfirmasi `GH_PROJECT_NUM` tidak berubah (`grep .workflow-kit.env`).
5. Sebut file **baru** yang perlu saya baca.
6. Jangan ubah kode fitur app.

## GitHub board / env

- Re-bootstrap **mempertahankan** `GH_PROJECT_NUM` dan `GH_PROJECT_OWNER` dari `.workflow-kit.env` yang ada.
- Hanya jalankan `--run-github-setup` jika saya minta (label/board hilang).
- Jangan simpan secret di `.workflow-kit.env`.

## Singkat

```text
Pull solo-dev-ai-kit terbaru, dry-run bootstrap (--target . --dry-run), lalu re-bootstrap (--target ., tanpa --force kecuali saya minta). Laporkan kit_version, konfirmasi GH_PROJECT_NUM tetap, tampilkan git diff. Jangan coding app.
```
